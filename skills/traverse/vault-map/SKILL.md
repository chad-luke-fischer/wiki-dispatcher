---
name: vault-map
description: "Orient in an unfamiliar or changed vault before any other traversal: census of folders, tags, hubs/MOCs, orphans, broken links, and the vault's own schema doc. Use first on every new task or new vault."
metadata:
  wd:
    family: traverse
    state: active
    pinned: false
    version: 0.1.0
---
# vault-map

Orient before you traverse. A vault is a graph with conventions; learn both in under 2k tokens.

## Steps
1. `vault_map` — folders, top tags, hub candidates, orphans, broken links.
2. Read the vault's schema doc if the system prompt did not already include it (`CLAUDE.md`, `AGENTS.md`, or `README.md` at the vault root via `vault_read`).
3. If an `index.md` / MOC exists among the hubs, `vault_read` it — it is the cheapest catalog of the whole vault.
4. Write a 5-line orientation to yourself: root MOC, folder roles (raw vs wiki vs daily), tag namespaces, date convention, anything odd.

## Rules
- Do this once per task, not once per question. Reuse the orientation.
- Trust the vault's schema doc over your assumptions about "llm-wiki" layouts; they vary.
- Orphans and broken links are signals, not errors to fix — mention them only when the task is lint or the answer depends on them.
