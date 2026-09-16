---
name: garden-evolve
description: "Explain and drive the skill-evolution loop (traces → pattern wiki → one proposal → eval gate → pending approval) when the user asks to improve skills from experience, review pending proposals, or understand why a skill changed."
metadata:
  wd:
    family: garden
    state: active
    pinned: false
    version: 0.1.0
---
# garden-evolve

The loop is implemented in code (`wd garden evolve`); your job is to run it well and explain it honestly.

## When asked to "improve skills" / "learn from that"
1. `garden_index()` — read the pattern index and the tail of the skill-impact ledger.
2. Check whether the relevant traces are rated. Unrated traces are sampled as neither failing nor passing; ask the user to `wd garden rate <trace> <1-5>` the ones that matter, or rate on their behalf if they describe the outcome.
3. Tell the user to run `wd garden evolve [--skill name]`. Do not hand-edit skills to simulate the loop; the loop exists so that changes are validated and staged.

## When asked about a pending proposal
- Read `/garden/pending/<id>/proposal.md`. Summarise: what changes, which patterns motivate it, baseline vs candidate scores (or UNVALIDATED if the skill has no evals yet — say that plainly), and your recommendation.
- Recommend adding 2-3 evals before approving an UNVALIDATED proposal on a skill that is used often.

## Invariants (say them when relevant)
- Wiki never rolls back; skills do.
- One atomic proposal per iteration.
- The inference agent (you, during a task) does not read the pattern wiki; only the proposer does.
- Rejected proposals are visible to the proposer so they are not re-proposed.
