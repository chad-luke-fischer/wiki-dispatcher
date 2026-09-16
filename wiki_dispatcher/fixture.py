"""Generate a small synthetic llm-wiki vault for tests and demos.

Shape follows the Karpathy pattern (raw/ immutable, wiki/ with index.md + log.md, entities/,
concepts/, sources/, synthesis/) plus Obsidian idioms (daily notes, a MOC, nested tags,
aliases, frontmatter links). It deliberately contains one orphan, one broken link, and one
contradiction so lint-style skills have something to find.
"""

from __future__ import annotations

from pathlib import Path

NOTES: dict[str, str] = {
    "CLAUDE.md": """# Vault schema

This is an llm-wiki. `raw/` is immutable. `wiki/` is LLM-maintained. Update `wiki/index.md`
and append to `wiki/log.md` on every ingest. Link generously with wikilinks. Start at [[index]].
""",
    "wiki/index.md": """---
type: moc
tags: [wiki/index]
---
# Index

## Concepts
- [[Context Engineering]] — packing the smallest high-signal token set for an agent
- [[Skill Evolution]] — skills co-evolving with a persistent pattern wiki
- [[Progressive Disclosure]] — metadata → body → resources, loaded just in time
- [[Lethal Trifecta]] — private data + untrusted content + external comms

## Entities
- [[Hermes Agent]] — Nous Research's self-improving CLI agent
- [[WikiSkill]] — Google Research paper on compiling experience into skills
- [[Obsidian]] — the vault editor

## Sources
- [[2026-04-04 Karpathy LLM Wiki]] — the founding gist
- [[2026-08-27 WikiSkill paper]] — arXiv 2608.27454

## Synthesis
- [[Why wikis beat RAG at small scale]]
""",
    "wiki/log.md": """# Log

## [2026-09-01] ingest | Karpathy LLM Wiki gist
## [2026-09-03] ingest | WikiSkill paper
## [2026-09-05] query | Why wikis beat RAG at small scale
""",
    "wiki/concepts/Context Engineering.md": """---
type: concept
tags: [wiki/concept, agents/context]
confidence: high
source_count: 2
up: "[[index]]"
---
# Context Engineering

Find the smallest possible set of high-signal tokens. Prefer just-in-time loading through
lightweight identifiers (paths, queries) over pre-loading everything. Closely related to
[[Progressive Disclosure]] and constrained by the [[Lethal Trifecta]].

Applied in [[WikiSkill]]: at most eight sampled traces, each capped at 15k characters.
See also [[Hermes Agent]] for a 60-character description index.
""",
    "wiki/concepts/Skill Evolution.md": """---
type: concept
tags: [wiki/concept, agents/skills]
confidence: medium
source_count: 2
up: "[[index]]"
---
# Skill Evolution

Skills improve by compiling experience: traces → pattern pages → one atomic proposal →
validation gate. [[WikiSkill]] rolls back skills but never the wiki. [[Hermes Agent]] instead
uses usage telemetry and a curator that archives stale skills.

Open question: how to handle neutral proposals that do not move the metric yet.
Related: [[Context Engineering]], [[Progressive Disclosure]].
""",
    "wiki/concepts/Progressive Disclosure.md": """---
type: concept
tags: [wiki/concept, agents/skills]
confidence: high
up: "[[index]]"
---
# Progressive Disclosure

Three layers: metadata (name + description) at startup, the SKILL.md body on invocation,
resources on demand. Keeps [[Context Engineering]] costs low as the skill count grows.
""",
    "wiki/concepts/Lethal Trifecta.md": """---
type: concept
tags: [wiki/concept, security]
confidence: high
---
# Lethal Trifecta

Private data + untrusted content + a channel to the outside. A wiki built from clipped
articles *is* untrusted content, so a query agent should be read-only and have no outbound
tools. See [[Context Engineering]].
""",
    "wiki/entities/Hermes Agent.md": """---
type: entity
tags: [wiki/entity, agents/harness]
aliases: [Hermes]
---
# Hermes Agent

Nous Research's CLI agent. Skills live in `~/.hermes/skills/`, self-written through a
background review fork, pruned by a curator. Descriptions are truncated at 60 characters in
the prompt index. Compare [[WikiSkill]]. Uses [[Progressive Disclosure]].

Claim: the curator runs weekly. (Contradicted by [[2026-08-27 WikiSkill paper]]? No — see
[[Skill Evolution]]; the contradiction is with [[Why wikis beat RAG at small scale]] which
says Hermes has a wiki. It does not.)
""",
    "wiki/entities/WikiSkill.md": """---
type: entity
tags: [wiki/entity, agents/skills]
---
# WikiSkill

arXiv 2608.27454. Three layers: raw traces, a pattern wiki (index, logs, skill-impact
ledger), and skills with PURPOSE.md. Source: [[2026-08-27 WikiSkill paper]].
Concepts: [[Skill Evolution]], [[Context Engineering]].
""",
    "wiki/entities/Obsidian.md": """---
type: entity
tags: [wiki/entity, tools]
---
# Obsidian

The editor for this vault. Graph view shows the shape of the wiki. Bases replace Dataview
for declarative queries. Mentioned by [[2026-04-04 Karpathy LLM Wiki]].
""",
    "wiki/sources/2026-04-04 Karpathy LLM Wiki.md": """---
type: source-summary
tags: [wiki/source]
date_updated: 2026-09-01
---
# Karpathy LLM Wiki (gist, 2026-04-04)

Three layers (raw, wiki, schema), three operations (ingest, query, lint). `index.md` is the
catalog, `log.md` the append-only journal. Recommends [[Obsidian]]. Seeds the ideas in
[[Context Engineering]] and [[Skill Evolution]].
""",
    "wiki/sources/2026-08-27 WikiSkill paper.md": """---
type: source-summary
tags: [wiki/source]
date_updated: 2026-09-03
---
# WikiSkill paper (arXiv 2608.27454)

Compiling Agent Experience into Persistent Knowledge for Skill Evolution. Entity page:
[[WikiSkill]]. Result: a 9B model with evolved skills beats a 27B model without.
Limitation: no wiki pruning; no skill retrieval evaluated. Feeds [[Skill Evolution]].
""",
    "wiki/synthesis/Why wikis beat RAG at small scale.md": """---
type: synthesis
tags: [wiki/synthesis]
---
# Why wikis beat RAG at small scale

Below a few hundred pages a flat [[index]] read by the model beats embeddings: fewer moving
parts, human-legible, compounding. Hermes keeps a wiki too (see [[Hermes Agent]]).
Beyond that, hybrid BM25 + vector + graph. See [[Context Engineering]].
""",
    "daily/2026-09-10.md": """---
tags: [daily]
---
# 2026-09-10

Read [[Skill Evolution]] again. Idea: a `garden-tend` skill that lists/adds/archives skills.
#idea/garden
""",
    "daily/2026-09-12.md": """---
tags: [daily]
---
# 2026-09-12

Sketched the dispatcher. Deliverables should be Obsidian-native markdown by default.
Link to [[Nonexistent Note]] to test broken-link detection. #idea/dispatcher
""",
    "wiki/concepts/Orphan Idea.md": """---
type: concept
tags: [wiki/concept]
confidence: low
---
# Orphan Idea

Nothing links here on purpose. A lint pass should notice.
""",
    "raw/karpathy-gist.txt": "Raw source placeholder (immutable). The gist text would live here.\n",
}


def make_fixture_vault(dest: Path) -> Path:
    dest = Path(dest)
    for rel, content in NOTES.items():
        p = dest / rel
        p.mkdir(parents=True, exist_ok=True) if p.suffix == "" else p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    (dest / ".obsidian").mkdir(exist_ok=True)
    (dest / ".obsidian" / "app.json").write_text("{}")
    return dest
