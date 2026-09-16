---
name: deliver-brief
description: "Decide the deliverable's kind and contract before writing anything: note, brief, report, outline, table, dataset, marp, canvas, mermaid, or wikipage. Always use at the start of a dispatch to restate the ask as a contract."
metadata:
  wd:
    family: deliver
    state: active
    pinned: true
    version: 0.1.0
---
# deliver-brief

Three lines before any traversal: **Kind · Audience · Done-when.**

## Steps
1. Read the deliverable contract in the system prompt (kind + instructions). If the user's ask clearly wants something else, say so in one line and follow the ask.
2. Write the contract to yourself:
   - Kind: one of note | brief | report | outline | table | dataset | marp | canvas | mermaid | wikipage
   - Audience: the user (Obsidian-native, terse) unless told otherwise
   - Done-when: 1-3 checkable conditions ("cites ≥3 notes", "one slide per concept", "CSV has columns x,y,z")
3. Pick the traversal: topical → `branch-extract`; broad → `hub-find`; categorical → `tag-lens`; temporal → `timeline-slice`; two-topic → `path-bridge`.
4. Traverse, then write. Check Done-when before answering.

## House style (all kinds)
- Obsidian-native: [[wikilinks]] for every vault note used; 2-4 `#tags` in a `tags:` line or at the end; no external links unless they came from the vault.
- Terse. Headings only when there are ≥3 sections. No throat-clearing.
- End with `Sources:` listing the [[notes]] drawn on, unless the kind forbids prose (dataset, canvas).
