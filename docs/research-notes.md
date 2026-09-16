---
type: research
title: Research notes — agentic architectures for wiki-dispatcher
created: 2026-09-16
tags: [project/wiki-dispatcher, research, agents/harness, agents/skills]
---

# Research notes (2026-09-16)

Three parallel research passes fed `PLAN.md`. Condensed here; primary sources at the end. Items marked UNVERIFIED were not confirmed against a primary source.

## A. Hermes Agent (Nous Research, v0.21.3, commit 416a8177)

- Skills: agentskills.io `SKILL.md` + `references/ templates/ scripts/ assets/`; frontmatter `metadata.hermes.{tags, category, requires_toolsets, config}`. Limits: name ≤64 `^[a-z0-9][a-z0-9._-]*$`, description ≤1024, content ≤100k chars. **Prompt index truncates descriptions to 60 chars** — routing dies past char 60.
- Layout: `~/.hermes/skills/<category>/<name>/`, plus `.usage.json` (telemetry), `.curator_ledger.jsonl`, `.archive/`, `~/.hermes/.curator_backups/blobs/` (sha256 before/after), `~/.hermes/pending/skills/` when `skills.write_approval: true`.
- Progressive disclosure: `<available_skills>` index → `skill_view(name)` → `skill_view(name, file_path)`.
- Creation: `skill_manage(create|patch|edit|delete|write_file|remove_file)` with **read-before-write enforced**; a `creation_nudge_interval`; `/learn`; a **background review fork** after turns (daemon thread, forked agent, whitelisted tools, ~30k tokens/event). Review prompt targets *class-level umbrella skills*; do-not-capture: environment failures, negative tool claims, transient errors, one-off narratives, unresolved failures.
- Curator: inactivity-triggered (168h interval, 2h idle). Phase 1 deterministic `active → stale (14d) → archived (30d)`; `use_count==0` never archived; pinned/cron skipped. Phase 2 (opt-in) LLM consolidation into umbrellas. Never delete; ledger + rollback.
- No fitness score; telemetry only: `use_count, view_count, patch_count, patch_generation, reuse_after_patch, created_by`. Advisory linter: incident-log shape (≥4 PR refs), references sprawl (>60 files).
- Memory: `MEMORY.md` (2.2k chars) + `USER.md` (1.4k), FTS5 session store; no wiki/graph store. "Memory = who the user is; skills = how to do this class of task."
- Lesson (PR #102920): literal self-improvement → 100k-char skill, 71 PR numbers, 443 reference files. Fix: *lessons, not incident logs*.
- "Skill garden" is not a Hermes term (UNVERIFIED as a concept there).

## B. Prime Agent and the 2026 skill-evolution literature

- Prime Agent (arXiv 2608.23552): L0 weights / L1 context / L2 persistent IPython REPL with recursive `rlm()` subagents / L3 disk skills+memory. Python-backed skills. "Continual Harness" (2605.09998): `/refine` post-turn review with before/after snapshots. Metrics: ARC-AGI-3 30%→95.5%. Cautionary tale: a Factorio agent preserved an exploit as a skill → they conclude refinement needs least privilege, independent validation, auditable rollback.
- Survey 2606.11435: paradigms = execution feedback, trajectory distillation, compression, RL. Best results: **separate failure diagnosis from rewrite generation; use external execution feedback**. SkillClaw (2604.08377), SkillFlow (2604.17308), SkillSmith (2606.01314), SkillOpt (2605.23904) — abstracts only.

## C. Karpathy LLM Wiki and community implementations

- Gist is prose-only; layout is co-designed. Layers: raw (immutable) / wiki / schema (`CLAUDE.md`). Ops: ingest / query / lint. `index.md` catalog, `log.md` append-only `## [date] op | title`. Index works to ~100s of pages; then qmd (BM25+vector).
- Community layout: `raw/`, `wiki/{index.md, log.md, overview.md, sources/, entities/, concepts/, synthesis/}`, `CLAUDE.md`. Frontmatter: `type: source-summary|entity|concept|synthesis`, `date_updated`, `source_count`, `confidence: high|medium|low`, tags `wiki/...`; jhinpan adds `status: raw|compiled|stale`.
- Failure modes: index ceiling (~77 pages felt; 100–500 claimed), agent ignores its own wiki ("check the knowledge base first" in every skill), batch ingest degrades, provenance drift / epistemic collapse, cross-entity contamination from hybrid retrieval, silent overwrite of contradictions, numeric confidence as false precision, auto-ingest assumes reliable LLMs (human write-gate).

## D. WikiSkill (arXiv 2608.27454)

- Layers: `raw/` traces; `wiki/{patterns/*.md, index.md, logs.md, skill-impact.md}`; `skills/<name>/{SKILL.md, PURPOSE.md}`.
- Index row: `[pattern](wiki/patterns/x.md): PROBLEM + ROOT CAUSE + FIX`. Pattern page: Trigger / Rule (failing + passing examples) / Anti-Pattern / evidence by iteration + task id.
- Algorithm 1: rollouts with skills (no wiki access) → sample ≤8 traces (≤5 fail, ≤3 pass, 15k chars) → Wiki Maintainer patches patterns → Skill Proposer (ReAct; reads index + skill-impact) emits ONE atomic proposal → accept iff val strictly improves → wiki updated with outcome, never rolled back.
- Results: Qwen-3.5-9B+WikiSkill 47.4 vs Qwen-3.6-27B no-skill 39.4; skills transfer across model families; wiki access for the inference agent lowers results (60.9 vs 63.7).
- Limitations: no retrieval/trigger eval, neutral proposals excluded, no wiki pruning, no very-long-horizon tasks.

## E. Vault traversal tooling

- Link kinds to parse: `[[Note]]`, `[[Note|alias]]`, `[[Note#Heading]]`, `![[embed]]`; resolve by lowercase stem / alias / shortest path.
- Libraries: obsidiantools (networkx graph, backlinks, frontmatter), obsidian-vault-graph (zero-dep CLI: neighbors --depth, centrality, orphans, qmd hybrid), fsck.com KG MCP (subgraph/paths/PageRank/betweenness), Obsidian CLI (needs the app), Bases/Dataview (no headless API), python-frontmatter, qmd, repomix (token counting only), networkx.
- Nobody ships budgeted branch extraction; recommended algorithm: best-first from seed over out-links + backlinks, depth ≤2, score = hop × edge-kind weight × recency, stop at token budget, always include seed + index row + MOC parents.
- Context engineering: smallest high-signal set; identifiers over content; progressive disclosure; context rot. Lethal trifecta: a wiki of clippings is untrusted content → query agent read-only, no outbound tools.

## F. Harness comparison

- **Claude Agent SDK** (Python 0.2.153 / TS 0.3.273): file-based skills (`.claude/skills/`, `setting_sources`, `plugins=`), subagents, hooks, sessions on disk, permission modes, `total_cost_usd`; no programmatic skill registration; API-key auth only for third-party apps.
- **deepagents** 0.7.14 (chosen): `create_deep_agent(model, tools, system_prompt, skills=[...], backend, permissions, subagents, checkpointer)`; `FilesystemBackend(root_dir, virtual_mode)`, `CompositeBackend(default, routes)`, `FilesystemPermission(operations, paths, mode=allow|deny|interrupt)`; skills must be directories of skill dirs; subagents can carry their own `skills`.
- Others: OpenAI Agents SDK (skills tied to sandbox), Google ADK (`SkillToolset`, explicit paths), pydantic-ai-harness (`Skills('.agents/skills')`), smolagents (proposal only), LangGraph/deepagents (spec-compliant, mounted root).
- Evals: skill-creator `evals.json` (with/without runs, `benchmark.json`), `claude plugin eval` (graders regex/tool_used/tool_order/file_exists/llm/baseline; `--json`; CI gate), `/skill-doctor` (context cost, never-invoked), promptfoo (`claude-agent-sdk` provider, `skill-used` assertion), inspect-ai, GEPA/`gepa.optimize_anything`, Karpathy autoresearch (one artifact, one scalar, keep-if-better, `results.tsv`).
- CLI config conventions: `~/.claude/`, `~/.codex/config.toml` + `.agents/skills`, `~/.hermes/{config.yaml, skills/, sessions/, state.db}`, opencode scans `.claude/skills` and `.agents/skills`, aider `.aider.conf.yml`. → `~/.wiki-dispatcher/{config.toml, usage.jsonl, vaults/, sessions/}`.

## Sources

- https://github.com/NousResearch/hermes-agent · https://hermes-agent.nousresearch.com/docs/user-guide/features/skills · …/curator · …/memory · https://github.com/NousResearch/hermes-agent/pull/102920
- https://github.com/PrimeIntellect-ai/prime-agent · https://arxiv.org/html/2608.23552
- https://arxiv.org/html/2606.11435v1 · https://arxiv.org/abs/2604.08377 · https://arxiv.org/html/2604.17308 · https://arxiv.org/html/2606.01314v1 · https://arxiv.org/pdf/2605.23904
- https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f · https://gist.github.com/kennyg/6c45cace2e1c4e424a28fcd51dd6c25b · https://gist.github.com/jhinpan/16f240dfce4b45532f28b5df829bc887 · https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2 · https://github.com/Astro-Han/karpathy-llm-wiki · https://github.com/ekadetov/llm-wiki · https://tomnguyenit.medium.com/i-built-karpathys-llm-wiki-for-my-day-job-here-s-what-actually-works-0d4ec6d1e433
- https://arxiv.org/abs/2608.27454 · https://arxiv.org/html/2608.27454v1 · https://github.com/kenhuangus/wikiskill
- https://github.com/mfarragher/obsidiantools · https://github.com/kartikkabadi/obsidian-vault-graph · https://blog.fsck.com/agent-blog/2026/03/20/knowledge-graph/ · https://github.com/kepano/obsidian-skills · https://blacksmithgu.github.io/obsidian-dataview/queries/structure/ · https://github.com/yamadashy/repomix
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents · https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- https://code.claude.com/docs/en/agent-sdk/overview · …/python · …/skills · …/plugins · …/hooks · …/sessions · …/cost-tracking · https://code.claude.com/docs/en/plugin-evals · https://code.claude.com/docs/en/skills
- https://agentskills.io/specification · https://agentskills.io/integrate-skills
- https://docs.langchain.com/oss/python/deepagents/overview · https://docs.langchain.com/oss/python/deepagents/skills
- https://openai.github.io/openai-agents-python/ref/sandbox/capabilities/skills/ · https://adk.dev/skills/ · https://pydantic.dev/docs/ai/harness/skills/ · https://github.com/huggingface/smolagents/discussions/1947
- https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md · https://www.promptfoo.dev/docs/providers/claude-agent-sdk/ · https://inspect.aisi.org.uk/agents.html · https://github.com/gepa-ai/gepa · https://github.com/karpathy/autoresearch/blob/master/program.md
- https://developers.openai.com/codex/config-basic · https://opencode.ai/docs/skills/ · https://aider.chat/docs/config/aider_conf.html
