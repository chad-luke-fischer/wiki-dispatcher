---
name: backlink-trace
description: "Follow inbound references to find who cites a note and in what context — for provenance questions ('where did this claim come from'), impact questions ('what depends on this'), and contradiction hunting."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# backlink-trace

Out-links say what a note *thinks*; backlinks say what the vault *thinks of it*.

## Steps
1. `vault_backlinks(note)` — list sources and link kinds.
2. For each source (cap 8, prefer wiki pages over daily notes), `vault_read` and quote the sentence containing the link. That sentence is the context of the citation.
3. Classify each citation: supports / extends / contradicts / merely mentions.
4. Report as a table: source · kind · one-line context · classification.

## Rules
- A note with many "merely mentions" backlinks is a hub, not an authority. Say so.
- Contradictions are the valuable output. Never silently pick a side — surface both with paths.
- Backlinks from `log.md`/daily notes tell you *when* something entered the vault; use them for timelines.
