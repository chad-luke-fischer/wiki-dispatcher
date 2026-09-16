---
name: path-bridge
description: "Connect two notes or ideas by finding the shortest link paths between them, then reading the notes along the way — for 'how does A relate to B' and for joining two branches into one deliverable."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# path-bridge

## Steps
1. Resolve both endpoints (search if needed).
2. `vault_paths(a, b, k=3)` — up to three shortest undirected paths.
3. `vault_read` the intermediate notes (they are the bridge concepts). If no path exists, say so and fall back to shared tags (`vault_neighbors` on each) — absence of a path is itself a finding.
4. Optionally `vault_mermaid([...])` for the deliverable.

## Rules
- The most interesting bridge is usually the one through a *concept* page, not the one through `index.md`. Skip paths that only go via the root hub.
