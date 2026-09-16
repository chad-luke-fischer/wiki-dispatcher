---
name: hub-find
description: "Locate map-of-content (MOC) and hub notes — the entry points that summarise a region of the vault — when the ask is broad ('what do I know about X') or when a branch keeps landing in the same neighbourhood."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# hub-find

Hubs are curated by the human; they are the highest-signal notes per token.

## Steps
1. `vault_hubs(limit=10)`; also `vault_frontmatter("type","moc")` and `vault_tag("moc")` — vaults name their hubs three different ways.
2. Pick the hub whose title or first paragraph matches the ask; `vault_read` it whole.
3. Use the hub's out-links as the seed set for `branch-extract` (depth 1) instead of searching.

## Rules
- `index.md` at the wiki root is the root hub in llm-wiki vaults; read it before anything else on broad asks.
- A hub with stale links (see `vault_map` broken-link list) is a lint finding; note it.
