"""Write a deliverable to disk with an Obsidian-native shell (frontmatter, tags, provenance).

Filenames: <out>/<YYYY-MM-DD> <slug>.<ext>. Every markdown deliverable gets frontmatter with
`type: deliverable`, `kind`, `tags: [dispatch/<kind>]`, `sources: ["[[...]]", ...]`, and the trace id
so it links back to the run that produced it. Canvas and datasets are written raw.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import frontmatter

from ..config import slugify

_FENCE = re.compile(r"```(?P<lang>\w+)?\s*\n(?P<body>.*?)```", re.S)
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def _sources(text: str) -> list[str]:
    seen, out = set(), []
    for m in _WIKILINK.finditer(text):
        t = m.group(1).strip()
        if t not in seen:
            seen.add(t)
            out.append(f"[[{t}]]")
    return out


def _fenced(text: str, lang: str) -> str | None:
    for m in _FENCE.finditer(text):
        if (m.group("lang") or "").lower() == lang:
            return m.group("body")
    return None


def write_deliverable(out_dir: Path, kind: str, message: str, content: str, trace_id: str, title: str | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    title = title or (message.strip().split("\n")[0][:60])
    slug = slugify(title)[:60]

    if kind == "canvas":
        body = _fenced(content, "json") or content
        p = out_dir / f"{date} {slug}.canvas"
        try:
            p.write_text(json.dumps(json.loads(body), indent=1))
        except json.JSONDecodeError:
            p = out_dir / f"{date} {slug}.canvas.md"
            p.write_text(content)
        return p

    if kind == "dataset":
        for lang, ext in (("csv", "csv"), ("json", "json")):
            if (body := _fenced(content, lang)) is not None:
                p = out_dir / f"{date} {slug}.{ext}"
                p.write_text(body)
                return p

    ext = "md"
    post = frontmatter.Post(content.strip() + "\n")
    post.metadata = {
        "type": "deliverable",
        "kind": kind,
        "title": title,
        "created": date,
        "trace": trace_id,
        "ask": message.strip()[:300],
        "tags": [f"dispatch/{kind}"],
        "sources": _sources(content),
    }
    if kind == "marp":
        post.metadata["marp"] = True
        # Marp wants its own frontmatter at the top; strip a duplicate one from the body
        post.content = re.sub(r"^---\s*\nmarp:\s*true\s*\n---\s*\n", "", post.content)
    p = out_dir / f"{date} {slug}.{ext}"
    p.write_text(frontmatter.dumps(post) + "\n")
    return p
