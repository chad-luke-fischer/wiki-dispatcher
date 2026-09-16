---
name: garden-tend
description: "Show, add, update, archive, restore, pin, and lint the garden's skills on request — the user-facing skill-management skill. Use whenever the user asks what skills exist or wants one changed."
metadata:
  wd:
    family: garden
    state: active
    pinned: true
    version: 0.1.0
---
# garden-tend

You are the gardener. The garden is the skill library; every change is ledgered and reversible.

## Show
- `skills_list()` → present as a table grouped by family: name · state · uses · patches · evals · description. Mention archived skills only if asked (`include_archived=True`).
- `skill_view(name)` for the body; `skill_view(name, "PURPOSE.md")` for why it exists; `skill_lint()` for hygiene.

## Add
1. Ask (or infer) family: traverse | garden | deliver | wiki. Name: kebab-case, class-level (`timeline-slice`, never `fix-for-august-bug`).
2. Draft: description (≤1024 chars, states *what* and *when*), body (rules + steps, <150 lines), PURPOSE.md (why; which patterns).
3. `skill_manage("create", ...)`. New skills start in state `seed`; they graduate to `active` once used.

## Update
1. `skill_manage` refuses a patch until you `skill_view` the target — read first, always.
2. Patch the smallest thing that fixes the problem. Write lessons as rules ("Prefer a second seed over depth 3 — depth 3 pulls tag siblings") not incident logs ("On 2026-09-12 the branch was too deep").
3. Give a `reason`; it lands in the ledger.

## Archive / restore / pin
- Archive, never delete. Pinned skills cannot be archived. `wd garden sweep` does the deterministic stale→archived lifecycle; you do not.

## Do not capture
Environment-dependent failures, transient errors, negative tool claims ("X does not work"), one-off narratives, unresolved failures. These harden into refusals the agent cites against itself for months.
