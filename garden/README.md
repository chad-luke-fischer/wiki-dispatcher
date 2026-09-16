# garden/

Open this folder in Obsidian. It is the dispatcher's memory about *how to work*, separate from
the user's vault (which is *what is known*).

```
garden/
  raw/traces/*.jsonl       immutable execution traces (one per run; rate with `wd garden rate`)
  wiki/index.md            pattern index — PROBLEM — ROOT CAUSE — fix
  wiki/patterns/*.md       root-caused lessons (Trigger / Rule / Anti-pattern / Evidence)
  wiki/logs.md             append-only journal
  wiki/skill-impact.md     proposal ledger with accept/reject history
  pending/<id>/            staged proposals: proposal.md, diff.patch, SKILL.md.new, meta.json
  ledger.jsonl             every skill mutation (actor, reason, before/after blob hashes)
  .blobs/                  content-addressed before/after snapshots (rollback material)
  .usage.json              per-skill telemetry: use/view/patch counts, created_by, reuse_after_patch
  .archive/                archived skills (never deleted)
```
