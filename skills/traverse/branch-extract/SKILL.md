---
name: branch-extract
description: "Pull a budgeted, cited branch of the vault around a seed note — the default way to gather context for any question that names a topic, note, or entity. Best-first over links, backlinks, and shared tags, depth-bounded."
metadata:
  wd:
    family: traverse
    state: active
    pinned: true
    version: 0.1.0
---
# branch-extract

The workhorse. Given a seed, get the connected neighbourhood that fits the budget, with provenance.

## Steps
1. Resolve the seed: if the ask names a note, use it. Otherwise `vault_search` (2-3 phrasings) and pick the top hit that is a wiki page, not a daily note.
2. `vault_branch(seed, depth=2, budget=<context budget>)` — returns a catalog + cited excerpts.
3. Scan the catalog. If the branch is dominated by one edge kind (all `tag:` siblings, or all backlinks from daily notes), tighten: re-run with `depth=1`, or pick a better seed from the catalog.
4. For anything truncated that matters, `vault_read` it whole.
5. Carry the catalog forward: every claim in the deliverable cites a `path` from it as a [[wikilink]].

## Budget discipline
- One branch ≈ 8k tokens by default. Two branches from different seeds beat one deep branch when the ask spans two topics (use `path-bridge` to connect them).
- Depth 3 is almost never worth it; prefer a second seed.
- Never paste raw branch output into the deliverable. Synthesize; cite.
