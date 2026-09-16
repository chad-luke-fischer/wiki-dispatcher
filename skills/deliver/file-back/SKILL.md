---
name: file-back
description: "Stage a new or updated wiki page for the mounted vault (Karpathy's 'query answers compound back into the wiki') — always human-gated; never writes to the vault directly. Use when the user says file it, add to the wiki, or ingest."
metadata:
  wd:
    family: deliver
    state: active
    pinned: false
    version: 0.1.0
---
# file-back

The vault is immutable to you. You stage; the human commits.

## Steps
1. Read the vault's schema doc and a sibling page of the same type to copy frontmatter and section conventions exactly.
2. Draft the page with [[wikilinks]] to existing pages (verify each with `vault_read`; a broken link is a lint finding you would be creating).
3. Draft the `index.md` row (`- [[Name]] — one-line summary`) and the `log.md` line (`## [YYYY-MM-DD] query | Title`).
4. Write all three to `/out/_wiki-staging/<Name>.md` (page) and `/out/_wiki-staging/<Name>.patch.md` (index + log additions).
5. Tell the user exactly which files to move and which lines to append. Do not claim the vault was updated.

## Rules
- If `write_vault = true` in config, writes to `/vault/**` interrupt for approval instead of being denied; still prefer staging for anything touching `index.md`.
- Mark inferences: a synthesis page gets `type: synthesis` and `confidence:` — never masquerade as a source summary.
