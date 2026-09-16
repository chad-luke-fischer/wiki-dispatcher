---
name: wiki-lint
description: "Health-check the mounted llm-wiki: broken links, orphans, index drift (pages missing from index.md), stale claims, contradictions between pages, and concepts mentioned but lacking a page. Use when asked to lint, audit, or tidy the vault."
metadata:
  wd:
    family: wiki
    state: active
    pinned: false
    version: 0.1.0
---
# wiki-lint

Eight checks, deterministic first, LLM last.

1. **Broken links** — `vault_map` → `broken_links`.
2. **Orphans** — `vault_map` → `orphans` (exclude `log.md`, daily notes, the schema doc).
3. **Index drift** — `vault_read("wiki/index.md")`; diff its links against `vault_frontmatter("type")` pages. Missing rows are findings.
4. **Dead index rows** — index links that resolve nowhere (subset of 1).
5. **Missing pages** — concepts that appear as `[[links]]` in ≥2 notes but have no page (from broken links, count sources).
6. **Stale** — `date_updated` older than the newest source that links to the page.
7. **Contradictions** — for the top 5 hubs, `backlink-trace` and flag citations classified *contradicts*.
8. **Confidence hygiene** — `confidence:` values that are numeric or missing on `type: concept`.

## Output
A report (kind=report) with one section per check, each finding as `- [[note]] — what — suggested fix`. Do not fix anything; `file-back` stages fixes if asked.
