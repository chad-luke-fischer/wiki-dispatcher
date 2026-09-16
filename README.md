# wiki-dispatcher

**Site:** https://chad-luke-fischer.github.io/wiki-dispatcher/ · source in `docs/index.html`, served by GitHub Pages from `main:/docs`. Publish or re-publish with `.\publish.ps1` (Windows) or `./publish.sh`.

A CLI-resident agent mounted to an [llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)-style Obsidian vault.
Given a message it traverses the vault, packs the relevant branch of context, and produces a
deliverable — while a garden of skills evolves from its own execution traces, gated by you.

Model-agnostic (LangChain `init_chat_model` strings; deepagents harness). See `PLAN.md` for
the architecture and the MVP plan.

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[anthropic,dev]"          # or [openai] / [ollama]
export ANTHROPIC_API_KEY=...               # or OPENAI_API_KEY / an Ollama model in config

wd fixture ./fixtures/generated/vault      # a tiny synthetic llm-wiki vault
wd mount ./fixtures/generated/vault        # writes ~/.wiki-dispatcher/config.toml, builds the index

wd vault map                               # no LLM: census, hubs, orphans, broken links
wd vault branch "Skill Evolution" --budget 4000
wd skills list

wd ask "Brief me on Skill Evolution and what it connects to"      # → <vault>/_dispatch/<date> brief.md
wd ask "Lay out the WikiSkill neighbourhood on a canvas" --as canvas
wd chat                                    # REPL; /save <kind>, /rate <1-5>, /quit

wd garden rate <trace-id> 2                # ratings make traces "failing"/"passing" for the loop
wd garden evolve --skill branch-extract    # maintain wiki → propose → validate on a copy → stage
wd garden pending && wd garden approve <id>
wd usage --days 7
```

Point it at a real vault with `wd mount ~/path/to/vault`. The vault is mounted **read-only**;
deliverables go to `<vault>/_dispatch/` (or `--out`). Set `write_vault = true` in
`~/.wiki-dispatcher/config.toml` to allow human-approved writes via the `file-back` skill.

## Layout

```
wiki_dispatcher/     the package   (cli · config · agent · llm · usage · trace · fixture)
  vault/             parse → index (SQLite FTS5) → graph (networkx) → pack → tools
  garden/            registry · ledger · evals · evolve · tools
  deliver/           router · writers
skills/<family>/<name>/SKILL.md   18 seed skills in 4 families (traverse · garden · deliver · wiki)
garden/              the pattern wiki (open in Obsidian): raw traces, patterns, ledgers, pending proposals
tests/               pytest, no API key needed
AGENTS.md            the dispatcher's operating schema (becomes the system prompt)
PLAN.md              architecture + research digest + MVP plan
```

## Models

`~/.wiki-dispatcher/config.toml`:

```toml
[models]
frontier = "anthropic:claude-sonnet-4-6"   # dispatch + synthesis + proposer
worker   = "anthropic:claude-haiku-4-5"    # traverser subagent, eval runs
cheap    = "ollama:qwen3:4b"               # wiki maintainer, judges — local if you like
```

Any `provider:model` accepted by LangChain's `init_chat_model` works. Costs are estimated from
the `[prices]` table and logged per run to `~/.wiki-dispatcher/usage.jsonl`.

## Tests

```bash
pytest -q        # 17 tests: index, graph, pack, registry, ledger, evals grading, evolve loop, deliverables
```
