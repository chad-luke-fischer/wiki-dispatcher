"""Deliverable kind inference. Cheap heuristics first; the agent can override via the
`deliver-brief` skill, and the user can force with `--as`.

Kinds (MVP): note | brief | report | outline | table | dataset | marp | canvas | mermaid | wikipage
"""

from __future__ import annotations

import re

KINDS = ("note", "brief", "report", "outline", "table", "dataset", "marp", "canvas", "mermaid", "wikipage")

_RULES: list[tuple[str, str]] = [
    (r"\b(slides?|deck|presentation|marp)\b", "marp"),
    (r"\b(canvas|board)\b", "canvas"),
    (r"\b(diagram|graph of|map of|mermaid|flowchart)\b", "mermaid"),
    (r"\b(csv|json|dataset|export|spreadsheet|rows)\b", "dataset"),
    (r"\b(table|compare|comparison|matrix)\b", "table"),
    (r"\b(report|deep[- ]dive|write[- ]?up|analysis)\b", "report"),
    (r"\b(outline|plan|steps|checklist|agenda)\b", "outline"),
    (r"\b(brief|summar(y|ize)|tl;?dr|overview)\b", "brief"),
    (r"\b(file (it|this) back|add to the wiki|new wiki page|ingest)\b", "wikipage"),
]


def infer_kind(message: str) -> str:
    m = message.lower()
    for pat, kind in _RULES:
        if re.search(pat, m):
            return kind
    return "note"


def kind_instructions(kind: str) -> str:
    return {
        "note": "Write an Obsidian-native markdown note: a clear H1, short sections, [[wikilinks]] to every vault note you drew on, and 2-4 #tags.",
        "brief": "Write a one-screen brief: 3-7 bullet takeaways first, then a short 'Why it matters', then 'Sources' as [[wikilinks]].",
        "report": "Write a structured report: Summary, Findings (with [[wikilink]] citations inline), Contradictions/Gaps found in the vault, Recommendations, Sources.",
        "outline": "Write a hierarchical outline (nested bullets, max depth 3). Each leaf cites its [[source note]].",
        "table": "Produce a markdown table. Columns should be the comparison dimensions; each row cites its [[source note]] in the last column.",
        "dataset": "Produce a fenced ```csv``` block (header row first) or ```json``` array — pick whichever the ask implies. No prose outside the fence except a one-line caption.",
        "marp": "Produce a Marp deck: start with '---\\nmarp: true\\n---', one idea per slide, '---' between slides, speaker notes as HTML comments, last slide = Sources with [[wikilinks]].",
        "canvas": "Produce a JSON Canvas (.canvas) document: {\"nodes\":[{\"id\",\"type\":\"file\"|\"text\",\"file\"|\"text\",\"x\",\"y\",\"width\",\"height\"}],\"edges\":[{\"id\",\"fromNode\",\"toNode\",\"label\"}]}. Use type:file nodes pointing at vault paths for real notes, text nodes for synthesis. Output ONLY the JSON in a ```json fence.",
        "mermaid": "Produce a Mermaid diagram in a ```mermaid fence (use vault_mermaid for the link structure, then annotate), followed by a 3-line legend.",
        "wikipage": "Draft a new wiki page in the vault's own conventions (read the vault's CLAUDE.md/AGENTS.md and index.md first). Include frontmatter matching sibling pages, [[wikilinks]] to related pages, and the index.md row + log.md line to add. Do NOT write to the vault; the file-back skill stages it for approval.",
    }[kind]
