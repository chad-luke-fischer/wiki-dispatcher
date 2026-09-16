---
name: tag-lens
description: "Slice the vault by tag or tag namespace (e.g. project/*, wiki/concept, #idea) to gather a set of notes that share a facet, then pack them. Use when the ask is categorical rather than topical."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# tag-lens

## Steps
1. `vault_map` shows the tag census; pick the tag or namespace prefix. `vault_tag("project")` matches `project/*`.
2. If more than ~12 notes, narrow: intersect with `vault_search` results or a frontmatter facet (`vault_frontmatter("status","active")`).
3. `vault_pack(paths, budget)` in priority order (most recently updated first unless the ask says otherwise).

## Rules
- Tags are namespaces in this vault family (`wiki/concept`, `agents/skills`). Respect the hierarchy when reporting: group by namespace.
- Frontmatter `tags:` and inline `#tags` are merged by the index; you do not need to read notes to get tags.
