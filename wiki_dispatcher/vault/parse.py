"""Parse a single markdown note: frontmatter, wikilinks, tags, headings, token estimate.

Handles `[[Note]]`, `[[Note|alias]]`, `[[Note#Heading]]`, `![[embed]]`, and `#tag` / `#nested/tag`
(outside code fences). Frontmatter `tags:` (list or string) and `aliases:` are merged in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

WIKILINK_RE = re.compile(r"(?P<embed>!?)\[\[(?P<target>[^\]|#]+)(?:#(?P<heading>[^\]|]+))?(?:\|(?P<alias>[^\]]+))?\]\]")
TAG_RE = re.compile(r"(?<![\w/#])#(?P<tag>[A-Za-z][\w/-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
FENCE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+\.md)\)")

_ENC = None


def count_tokens(text: str) -> int:
    """tiktoken cl100k if available, else a words*1.3 estimate. Good enough for budgeting."""
    global _ENC
    if _ENC is None:
        try:
            import tiktoken

            _ENC = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover
            _ENC = False
    if _ENC:
        return len(_ENC.encode(text, disallowed_special=()))
    return int(len(text.split()) * 1.3)


@dataclass
class Link:
    target: str  # raw target as written (no extension)
    kind: str  # body | embed | frontmatter | mdlink
    heading: str | None = None
    alias: str | None = None


@dataclass
class ParsedNote:
    path: str  # vault-relative posix path
    title: str
    body: str
    frontmatter: dict = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    aliases: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    words: int = 0
    tokens: int = 0
    mtime: float = 0.0


def _strip_code(text: str) -> str:
    return FENCE_RE.sub(" ", text)


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [t.strip() for t in re.split(r"[,\s]+", v) if t.strip()]
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v)]


def parse_note(abs_path: Path, vault_root: Path) -> ParsedNote:
    rel = abs_path.relative_to(vault_root).as_posix()
    raw = abs_path.read_text(encoding="utf-8", errors="replace")
    try:
        post = frontmatter.loads(raw)
        fm, body = dict(post.metadata), post.content
    except Exception:
        fm, body = {}, raw

    note = ParsedNote(path=rel, title=abs_path.stem, body=body, frontmatter=fm)
    note.mtime = abs_path.stat().st_mtime
    if isinstance(fm.get("title"), str):
        note.title = fm["title"]

    clean = _strip_code(body)
    for m in WIKILINK_RE.finditer(clean):
        note.links.append(
            Link(
                target=m.group("target").strip(),
                kind="embed" if m.group("embed") else "body",
                heading=m.group("heading"),
                alias=m.group("alias"),
            )
        )
    for m in MD_LINK_RE.finditer(clean):
        note.links.append(Link(target=m.group(1).removesuffix(".md"), kind="mdlink"))
    for m in TAG_RE.finditer(clean):
        note.tags.add(m.group("tag").strip("/").lower())
    for t in _as_list(fm.get("tags")) + _as_list(fm.get("tag")):
        note.tags.add(t.lstrip("#").strip("/").lower())
    note.aliases = _as_list(fm.get("aliases")) + _as_list(fm.get("alias"))

    # frontmatter wikilinks (e.g. `up: "[[MOC]]"`, `related: ["[[a]]", "[[b]]"]`)
    for k, v in fm.items():
        if k in ("tags", "tag", "aliases", "alias"):
            continue
        for s in _as_list(v) if not isinstance(v, str) else [v]:
            for m in WIKILINK_RE.finditer(str(s)):
                note.links.append(Link(target=m.group("target").strip(), kind="frontmatter"))

    note.headings = [h.strip() for _, h in HEADING_RE.findall(body)]
    note.words = len(body.split())
    note.tokens = count_tokens(body)
    return note
