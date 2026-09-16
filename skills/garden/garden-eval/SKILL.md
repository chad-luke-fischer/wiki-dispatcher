---
name: garden-eval
description: "Write or extend evals for a skill (evals/evals.json) so the evolve loop has a metric — use when a skill is UNVALIDATED, when the user asks to test a skill, or after a skill is used for something that would make a good regression case."
metadata:
  wd:
    family: garden
    state: active
    pinned: false
    version: 0.1.0
---
# garden-eval

No metric, no evolution. Evals are small, cheap, and deterministic-first.

## Format (`evals/evals.json`)
```json
[{"id": "kebab-id", "prompt": "the user message", "expected": "one line for humans",
  "assertions": [
    {"type": "contains", "value": "text"}, {"type": "regex", "value": "pattern"},
    {"type": "tool_used", "value": "vault_branch"}, {"type": "skill_used", "value": "branch-extract"},
    {"type": "max_tool_calls", "value": "8"}, {"type": "llm_rubric", "value": "judge sentence"}]}]
```

## Steps
1. `skill_view(name)` and `skill_view(name, "evals/evals.json")` (may not exist).
2. Write 2-4 cases that exercise the skill's *rules*, not just its happy path: one budget/limit case, one "should refuse or narrow" case.
3. Prefer `tool_used`, `regex`, `max_tool_calls` (free) over `llm_rubric` (costs a cheap-model call).
4. Prompts must be answerable from the mounted vault. For the fixture vault, `Skill Evolution`, `Context Engineering`, `Hermes Agent` are safe seeds.
5. `skill_manage("write_file", name, file="evals/evals.json", content=...)`.

## Rules
- Score = fraction of assertions passed, averaged over cases. The gate needs a *strict* improvement, so avoid all-or-nothing single-case evals.
