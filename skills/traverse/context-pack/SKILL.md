---
name: context-pack
description: "Assemble the final, budgeted, cited context brief from any set of notes gathered by other traverse skills — the hand-off contract between traversal and deliverable writing."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# context-pack

Every deliverable skill consumes a pack; every traverse skill produces paths for one.

## Contract
A pack is markdown with two sections: `## Catalog` (one line per note: path, title, tokens, why it is here, first sentence) and `## Notes` (bodies, highest priority first, tail truncated/omitted). `vault_branch` and `vault_pack` emit this shape.

## Steps
1. Order paths: seed → direct links → hubs → backlinks → tag siblings. Recency breaks ties.
2. `vault_pack(paths, budget)`. If `Omitted` is non-empty and contains something the ask needs, drop lower-priority notes and re-pack rather than raising the budget.
3. Add a 3-line synthesis at the top: what the pack covers, what it does not, and the single most load-bearing note.

## Rules
- Never exceed the configured budget; two smaller packs beat one big one.
- The catalog is what you cite from. Keep it verbatim in your working notes.
