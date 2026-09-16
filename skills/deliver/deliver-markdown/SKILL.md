---
name: deliver-markdown
description: "Write note, brief, report, outline, and table deliverables in Obsidian-native markdown with frontmatter-friendly structure, wikilink citations, and tags. Default deliverable skill."
metadata:
  wd:
    family: deliver
    state: active
    pinned: false
    version: 0.1.0
---
# deliver-markdown

## Shape by kind
- **note**: H1, 2-5 short sections, [[links]] inline, tags at the end.
- **brief**: 3-7 takeaway bullets → "Why it matters" (3 lines) → Sources.
- **report**: Summary → Findings (cite inline) → Contradictions & gaps *found in the vault* → Recommendations → Sources.
- **outline**: nested bullets, depth ≤3, leaves cite.
- **table**: dimensions as columns, last column = source [[link]].

## Rules
- Cite with the note's *name* as written in the vault (`[[Skill Evolution]]`), not the path; the index resolves both but names render in Obsidian.
- Distinguish what the vault says from what you infer: "The vault says… / I infer…". Provenance drift is the enemy.
- If two notes contradict, that is a finding; put it under Contradictions, never resolve it silently.
- Keep the whole deliverable under ~800 words unless the kind is report.
