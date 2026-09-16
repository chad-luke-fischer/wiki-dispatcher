---
name: timeline-slice
description: "Reconstruct what happened over a date range from daily notes, log.md entries, and dated frontmatter — for 'what did I do in August', 'when did X enter the vault', and change-over-time questions."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# timeline-slice

## Steps
1. Find the journal: `vault_read("wiki/log.md")` if present (append-only `## [YYYY-MM-DD] op | title` lines), plus `vault_tag("daily")` or a `daily/` folder from `vault_map`.
2. Filter to the range by filename/date prefix; `vault_frontmatter("date_updated")` catches dated wiki pages.
3. `vault_pack` the slice chronologically. Summarise as a dated list; each entry cites its note.

## Rules
- Prefer the log for *what entered the wiki*; prefer daily notes for *what the human was doing*. Say which you used.
- Do not infer dates from prose. If a note has no date, say "undated".
