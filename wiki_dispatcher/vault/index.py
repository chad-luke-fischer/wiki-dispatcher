"""SQLite + FTS5 index of a vault, plus link resolution.

Cache lives outside the vault by default (config.index_db) so the vault stays clean.
Incremental: notes are re-parsed only when mtime changes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .parse import ParsedNote, parse_note

IGNORED_DIRS = {".obsidian", ".git", ".trash", ".wiki-dispatcher", "node_modules", ".dispatcher"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, folder TEXT, mtime REAL, words INT, tokens INT,
  frontmatter TEXT, headings TEXT, aliases TEXT
);
CREATE TABLE IF NOT EXISTS links (
  src TEXT, dst TEXT, kind TEXT, raw TEXT, resolved INT
);
CREATE INDEX IF NOT EXISTS links_src ON links(src);
CREATE INDEX IF NOT EXISTS links_dst ON links(dst);
CREATE TABLE IF NOT EXISTS tags (path TEXT, tag TEXT);
CREATE INDEX IF NOT EXISTS tags_tag ON tags(tag);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(path UNINDEXED, title, body, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


@dataclass
class NoteRow:
    path: str
    title: str
    folder: str
    words: int
    tokens: int
    frontmatter: dict
    headings: list[str]
    aliases: list[str]
    mtime: float

    @property
    def stem(self) -> str:
        return Path(self.path).stem


class VaultIndex:
    def __init__(self, vault: Path, db_path: Path):
        self.vault = Path(vault)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    # ---- building -------------------------------------------------------
    def iter_md(self):
        for p in self.vault.rglob("*.md"):
            if any(part in IGNORED_DIRS for part in p.relative_to(self.vault).parts):
                continue
            yield p

    def build(self, rebuild: bool = False) -> dict:
        """(Re)index the vault. Returns stats."""
        if rebuild:
            for t in ("notes", "links", "tags", "notes_fts"):
                self.con.execute(f"DELETE FROM {t}")
        known = {r["path"]: r["mtime"] for r in self.con.execute("SELECT path, mtime FROM notes")}
        seen, updated = set(), 0
        parsed: list[ParsedNote] = []
        for p in self.iter_md():
            rel = p.relative_to(self.vault).as_posix()
            seen.add(rel)
            if not rebuild and known.get(rel) == p.stat().st_mtime:
                continue
            parsed.append(parse_note(p, self.vault))
            updated += 1
        removed = set(known) - seen
        for rel in removed:
            self._delete(rel)
        for n in parsed:
            self._upsert(n)
        # link resolution needs the full name table, so do it after all upserts
        self._resolve_links()
        self.con.execute("INSERT OR REPLACE INTO meta VALUES ('vault', ?)", (str(self.vault),))
        self.con.commit()
        return {"indexed": updated, "removed": len(removed), "total": self.count()}

    def _delete(self, rel: str) -> None:
        for t in ("notes", "links", "tags", "notes_fts"):
            col = "src" if t == "links" else "path"
            self.con.execute(f"DELETE FROM {t} WHERE {col}=?", (rel,))

    def _upsert(self, n: ParsedNote) -> None:
        self._delete(n.path)
        folder = str(Path(n.path).parent.as_posix())
        self.con.execute(
            "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?)",
            (
                n.path,
                n.title,
                "" if folder == "." else folder,
                n.mtime,
                n.words,
                n.tokens,
                json.dumps(n.frontmatter, default=str),
                json.dumps(n.headings),
                json.dumps(n.aliases),
            ),
        )
        self.con.executemany(
            "INSERT INTO links VALUES (?,?,?,?,0)",
            [(n.path, "", lk.kind, lk.target) for lk in n.links],
        )
        self.con.executemany("INSERT INTO tags VALUES (?,?)", [(n.path, t) for t in n.tags])
        self.con.execute("INSERT INTO notes_fts VALUES (?,?,?)", (n.path, n.title, n.body))

    def _name_table(self) -> dict[str, str]:
        """lowercase stem / alias / full relative path (no .md) -> path. Shortest path wins ties."""
        table: dict[str, str] = {}
        rows = sorted(self.con.execute("SELECT path, aliases FROM notes"), key=lambda r: len(r["path"]))
        for r in rows:
            p = r["path"]
            keys = {Path(p).stem.lower(), p.removesuffix(".md").lower()}
            keys |= {a.lower() for a in json.loads(r["aliases"] or "[]")}
            for k in keys:
                table.setdefault(k, p)
        return table

    def _resolve_links(self) -> None:
        table = self._name_table()
        rows = list(self.con.execute("SELECT rowid, raw FROM links"))
        for r in rows:
            raw = r["raw"].strip().removesuffix(".md")
            dst = table.get(raw.lower()) or table.get(Path(raw).name.lower())
            self.con.execute(
                "UPDATE links SET dst=?, resolved=? WHERE rowid=?",
                (dst or raw, 1 if dst else 0, r["rowid"]),
            )

    # ---- reading --------------------------------------------------------
    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

    def _row(self, r) -> NoteRow:
        return NoteRow(
            path=r["path"],
            title=r["title"],
            folder=r["folder"],
            words=r["words"],
            tokens=r["tokens"],
            frontmatter=json.loads(r["frontmatter"] or "{}"),
            headings=json.loads(r["headings"] or "[]"),
            aliases=json.loads(r["aliases"] or "[]"),
            mtime=r["mtime"],
        )

    def get(self, path_or_name: str) -> NoteRow | None:
        r = self.con.execute("SELECT * FROM notes WHERE path=?", (path_or_name,)).fetchone()
        if r:
            return self._row(r)
        resolved = self.resolve(path_or_name)
        if resolved:
            r = self.con.execute("SELECT * FROM notes WHERE path=?", (resolved,)).fetchone()
            return self._row(r) if r else None
        return None

    def resolve(self, name: str) -> str | None:
        name = name.strip().removesuffix(".md").lower()
        table = self._name_table()
        return table.get(name) or table.get(Path(name).name)

    def all_notes(self) -> list[NoteRow]:
        return [self._row(r) for r in self.con.execute("SELECT * FROM notes ORDER BY path")]

    def read(self, path: str) -> str:
        return (self.vault / path).read_text(encoding="utf-8", errors="replace")

    def outlinks(self, path: str) -> list[tuple[str, str]]:
        """[(dst_path, kind)] for resolved links out of `path`."""
        return [
            (r["dst"], r["kind"])
            for r in self.con.execute("SELECT DISTINCT dst, kind FROM links WHERE src=? AND resolved=1", (path,))
        ]

    def backlinks(self, path: str) -> list[tuple[str, str]]:
        return [
            (r["src"], r["kind"])
            for r in self.con.execute("SELECT DISTINCT src, kind FROM links WHERE dst=? AND resolved=1", (path,))
        ]

    def broken_links(self) -> list[tuple[str, str]]:
        return [(r["src"], r["raw"]) for r in self.con.execute("SELECT src, raw FROM links WHERE resolved=0")]

    def orphans(self) -> list[str]:
        return [
            r["path"]
            for r in self.con.execute(
                "SELECT path FROM notes WHERE path NOT IN (SELECT dst FROM links WHERE resolved=1)"
            )
        ]

    def tags_of(self, path: str) -> list[str]:
        return [r["tag"] for r in self.con.execute("SELECT tag FROM tags WHERE path=?", (path,))]

    def notes_with_tag(self, tag: str, prefix: bool = True) -> list[str]:
        tag = tag.lstrip("#").lower()
        q = "SELECT DISTINCT path FROM tags WHERE tag=? OR tag LIKE ?" if prefix else "SELECT DISTINCT path FROM tags WHERE tag=?"
        args = (tag, f"{tag}/%") if prefix else (tag,)
        return [r["path"] for r in self.con.execute(q, args)]

    def tag_census(self) -> list[tuple[str, int]]:
        return [
            (r["tag"], r["n"])
            for r in self.con.execute("SELECT tag, COUNT(*) n FROM tags GROUP BY tag ORDER BY n DESC")
        ]

    def folder_census(self) -> list[tuple[str, int]]:
        return [
            (r["folder"], r["n"])
            for r in self.con.execute("SELECT folder, COUNT(*) n FROM notes GROUP BY folder ORDER BY n DESC")
        ]

    def search(self, query: str, limit: int = 10) -> list[tuple[str, str, float]]:
        """FTS5 BM25 search -> [(path, snippet, score)]. Lower score is better (bm25 convention)."""
        try:
            rows = self.con.execute(
                "SELECT path, snippet(notes_fts, 2, '«', '»', '…', 12) AS snip, bm25(notes_fts) AS score "
                "FROM notes_fts WHERE notes_fts MATCH ? ORDER BY score LIMIT ?",
                (query, limit),
            )
            return [(r["path"], r["snip"], r["score"]) for r in rows]
        except sqlite3.OperationalError:
            # fall back to a quoted phrase if the query has FTS syntax characters
            rows = self.con.execute(
                "SELECT path, snippet(notes_fts, 2, '«', '»', '…', 12) AS snip, bm25(notes_fts) AS score "
                "FROM notes_fts WHERE notes_fts MATCH ? ORDER BY score LIMIT ?",
                (f'"{query}"', limit),
            )
            return [(r["path"], r["snip"], r["score"]) for r in rows]

    def frontmatter_query(self, key: str, value: str | None = None) -> list[str]:
        out = []
        for n in self.all_notes():
            v = n.frontmatter.get(key)
            if v is None:
                continue
            if value is None or str(v).lower() == value.lower() or (isinstance(v, list) and value in [str(x) for x in v]):
                out.append(n.path)
        return out
