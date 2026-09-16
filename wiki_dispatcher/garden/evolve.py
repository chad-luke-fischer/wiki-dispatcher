"""WikiSkill-style evolution loop, human-gated.

    traces (raw/)  ──►  Wiki Maintainer  ──►  wiki/patterns/*.md + index.md + logs.md
                                    │
                                    ▼
                          Skill Proposer (reads index + skill-impact + catalog)
                                    │  ONE atomic proposal
                                    ▼
                    apply on a COPY of skills/  ──►  evals: baseline vs candidate
                                    │
                                    ▼
                     garden/pending/<id>/  (proposal.md, SKILL.md.new, diff.patch, meta.json)
                                    │
                        `wd garden approve <id>` / `reject <id>`   ← the human gate
                                    │
                                    ▼
                    skills/ updated via registry (ledgered) ; skill-impact.md appended

Design choices carried from the research:
- Wiki is never rolled back; skills are (WikiSkill).
- The inference agent never reads the pattern wiki during a task (WikiSkill ablation: it hurts).
- Proposer sees the full acceptance history so rejected ideas are not re-proposed.
- Lessons, not incident logs (Hermes PR #102920): the proposer is told to write rules.
- Neutral proposals (no metric change) are staged as UNVALIDATED rather than dropped, since
  many skills will not have evals yet; the human decides.

The maintainer/proposer are injectable callables so the loop is testable without an API key.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import frontmatter

from ..trace import TraceWriter
from .evals import Runner, load_cases, run_evals
from .registry import SkillRegistry

MAINTAINER_SYSTEM = """You are the Wiki Maintainer for an agent's skill garden.
You read execution traces and compile them into durable PATTERN pages. A pattern is a specific
failure mode or successful strategy with an actionable rule. Root-cause failures; do not narrate.
Never write negative tool claims ("X does not work"); write the working path instead.
Reply with JSON only:
{"patterns": [{"name": "kebab-case-name", "problem": "...", "root_cause": "...", "fix": "...",
  "trigger": "when this applies", "rule": "imperative rule + one clause of why",
  "anti_pattern": "what not to do", "evidence": ["trace-id", ...], "skills": ["skill-name", ...]}],
 "log": "one-line summary of this maintenance pass"}
Return an empty patterns list if the traces contain nothing durable."""

PROPOSER_SYSTEM = """You are the Skill Proposer. You read the pattern-wiki index, the skill-impact
ledger (what was accepted/rejected before), and the skill catalog, then emit EXACTLY ONE atomic
proposal that would most improve future task performance. Prefer patching an existing skill over
creating one. Do not re-propose rejected ideas. Write lessons as rules, not incident logs.
Reply with JSON only:
{"skill": "existing-or-new-name", "family": "traverse|garden|deliver|wiki", "change_type": "patch|create",
 "rationale": "why, citing pattern names", "patterns": ["pattern-name", ...],
 "description": "full new description (<=1024 chars)",
 "skill_md_body": "the COMPLETE new SKILL.md body (markdown, no frontmatter)",
 "purpose_md": "complete PURPOSE.md text"}
If nothing is worth proposing, reply {"skill": null, "rationale": "..."}."""


@dataclass
class Proposal:
    id: str
    skill: str
    family: str
    change_type: str
    rationale: str
    patterns: list[str]
    description: str
    body: str
    purpose: str
    baseline: float | None = None
    candidate: float | None = None
    status: str = "PENDING"  # PENDING | ACCEPTED | REJECTED | UNVALIDATED


class Garden:
    def __init__(self, reg: SkillRegistry, traces: TraceWriter, maintainer: Callable[[str, str], dict] | None = None, proposer: Callable[[str, str], dict] | None = None, models: dict | None = None):
        self.reg = reg
        self.traces = traces
        self.wiki = reg.garden / "wiki"
        self.patterns = self.wiki / "patterns"
        self.patterns.mkdir(parents=True, exist_ok=True)
        self.models = models or {}
        self._maintainer = maintainer or self._llm_maintainer
        self._proposer = proposer or self._llm_proposer

    # ---- LLM defaults -------------------------------------------------
    def _llm_maintainer(self, system: str, user: str) -> dict:
        from ..llm import complete, extract_json

        text, _ = complete(self.models.get("cheap") or self.models["frontier"], system, user)
        return extract_json(text)

    def _llm_proposer(self, system: str, user: str) -> dict:
        from ..llm import complete, extract_json

        text, _ = complete(self.models["frontier"], system, user, temperature=0.4)
        return extract_json(text)

    # ---- wiki files ---------------------------------------------------
    def index_text(self) -> str:
        p = self.wiki / "index.md"
        return p.read_text() if p.exists() else "# Garden index\n"

    def impact_text(self) -> str:
        p = self.wiki / "skill-impact.md"
        return p.read_text() if p.exists() else "# Skill impact ledger\n"

    def _append(self, rel: str, text: str) -> None:
        p = self.wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(text)

    def write_pattern(self, pat: dict) -> Path:
        name = re.sub(r"[^a-z0-9-]", "-", pat["name"].lower()).strip("-")
        p = self.patterns / f"{name}.md"
        existing = frontmatter.load(p) if p.exists() else None
        evidence = sorted(set((existing.metadata.get("evidence", []) if existing else []) + pat.get("evidence", [])))
        post = frontmatter.Post(
            f"""# {name}

**Problem.** {pat['problem']}

**Root cause.** {pat['root_cause']}

**Fix.** {pat['fix']}

## Trigger
{pat.get('trigger', '')}

## Rule
{pat.get('rule', '')}

## Anti-pattern
{pat.get('anti_pattern', '')}

## Evidence
{chr(10).join(f'- trace `{e}`' for e in evidence) or '- (none recorded)'}
""",
            type="pattern",
            tags=["garden/pattern"] + [f"skill/{s}" for s in pat.get("skills", [])],
            skills=pat.get("skills", []),
            evidence=evidence,
            updated=time.strftime("%Y-%m-%d"),
        )
        p.write_text(frontmatter.dumps(post) + "\n")
        # index row: [name](wiki/patterns/name.md): PROBLEM + ROOT CAUSE + FIX
        row = f"- [[patterns/{name}|{name}]]: {pat['problem']} — {pat['root_cause']} — **fix:** {pat['fix']}\n"
        idx = self.wiki / "index.md"
        text = self.index_text()
        text = re.sub(rf"^- \[\[patterns/{re.escape(name)}\|.*$\n?", "", text, flags=re.M)
        if "## Patterns" not in text:
            text += "\n## Patterns\n\n"
        idx.write_text(text.rstrip("\n") + "\n" + row)
        return p

    # ---- step 1: maintain --------------------------------------------
    def maintain(self, since_trace: str | None = None, skill: str | None = None) -> list[Path]:
        sample = self.traces.sample(since_trace=since_trace, skill=skill)
        if not sample:
            return []
        user = f"EXISTING INDEX:\n{self.index_text()}\n\nTRACES ({len(sample)}):\n" + "\n\n".join(json.dumps(t) for t in sample)
        out = self._maintainer(MAINTAINER_SYSTEM, user)
        written = [self.write_pattern(p) for p in out.get("patterns", [])]
        self._append("logs.md", f"## [{time.strftime('%Y-%m-%d %H:%M')}] maintain | {out.get('log', '')} | traces={[t['id'] for t in sample]} | patterns={[w.stem for w in written]}\n")
        return written

    # ---- step 2: propose ---------------------------------------------
    def propose(self, target: str | None = None) -> Proposal | None:
        catalog = "\n".join(f"- {s.name} [{s.family}, {s.state}, uses={s.usage.get('use_count', 0)}]: {s.description}" for s in self.reg.all())
        focus = ""
        if target and (s := self.reg.get(target)):
            focus = f"\n\nTARGET SKILL {target} — current SKILL.md:\n{s.skill_md.read_text()}\n\nPURPOSE.md:\n{s.purpose()}"
        user = f"INDEX:\n{self.index_text()}\n\nSKILL-IMPACT LEDGER:\n{self.impact_text()[-6000:]}\n\nCATALOG:\n{catalog}{focus}"
        out = self._proposer(PROPOSER_SYSTEM, user)
        if not out.get("skill"):
            self._append("logs.md", f"## [{time.strftime('%Y-%m-%d %H:%M')}] propose | nothing proposed | {out.get('rationale', '')}\n")
            return None
        return Proposal(
            id=time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4],
            skill=out["skill"],
            family=out.get("family", "traverse"),
            change_type=out.get("change_type", "patch"),
            rationale=out.get("rationale", ""),
            patterns=out.get("patterns", []),
            description=out.get("description", ""),
            body=out.get("skill_md_body", ""),
            purpose=out.get("purpose_md", ""),
        )

    # ---- step 3: validate on a copy ----------------------------------
    def validate(self, prop: Proposal, runner_factory: Callable[[Path], Runner] | None, judge_model: str | None = None) -> Proposal:
        """runner_factory(skills_root) -> runner(prompt). If None or no evals: UNVALIDATED."""
        existing = self.reg.get(prop.skill)
        cases = load_cases(existing.path) if existing else []
        if not runner_factory or not cases:
            prop.status = "UNVALIDATED"
            return prop
        tmp = Path(tempfile.mkdtemp(prefix="wd-evolve-"))
        cand_root = tmp / "skills"
        shutil.copytree(self.reg.root, cand_root)
        cand_reg = SkillRegistry(cand_root, tmp / "garden")
        if prop.change_type == "create" or not existing:
            cand_reg.create(prop.skill, prop.family, prop.description, prop.body, prop.purpose, actor="evolve")
        else:
            cand_reg.update(prop.skill, description=prop.description or None, body=prop.body or None, purpose=prop.purpose or None, actor="evolve")
        base = run_evals(prop.skill, cases, runner_factory(self.reg.root), judge_model)
        cand = run_evals(prop.skill, cases, runner_factory(cand_root), judge_model)
        prop.baseline, prop.candidate = round(base.score, 3), round(cand.score, 3)
        prop.status = "PENDING" if prop.candidate > prop.baseline else "PENDING-NO-GAIN"
        shutil.rmtree(tmp, ignore_errors=True)
        return prop

    # ---- step 4: stage for the human ---------------------------------
    def stage(self, prop: Proposal) -> Path:
        d = self.reg.garden / "pending" / prop.id
        d.mkdir(parents=True, exist_ok=True)
        existing = self.reg.get(prop.skill)
        before = existing.body() if existing else ""
        diff = "".join(difflib.unified_diff(before.splitlines(True), prop.body.splitlines(True), fromfile=f"{prop.skill}/SKILL.md", tofile=f"{prop.skill}/SKILL.md (proposed)"))
        (d / "diff.patch").write_text(diff)
        (d / "SKILL.md.new").write_text(prop.body)
        (d / "PURPOSE.md.new").write_text(prop.purpose)
        (d / "meta.json").write_text(json.dumps(prop.__dict__, indent=1))
        (d / "proposal.md").write_text(
            f"""---
type: proposal
status: {prop.status}
skill: "[[{prop.skill}]]"
tags: [garden/proposal]
---
# Proposal {prop.id} — {prop.change_type} `{prop.skill}`

**Status:** {prop.status}  **Baseline:** {prop.baseline}  **Candidate:** {prop.candidate}

## Rationale
{prop.rationale}

## Motivating patterns
{chr(10).join(f'- [[patterns/{p}|{p}]]' for p in prop.patterns) or '- (none cited)'}

## Diff
```diff
{diff or '(new skill)'}
```

Approve with `wd garden approve {prop.id}` · reject with `wd garden reject {prop.id} --reason "..."`
"""
        )
        self._append("skill-impact.md", f"\n## {prop.id} | {prop.change_type} {prop.skill} | {prop.status}\n- baseline={prop.baseline} candidate={prop.candidate}\n- patterns: {', '.join(prop.patterns)}\n- rationale: {prop.rationale[:300]}\n")
        return d

    def pending(self) -> list[dict]:
        out = []
        for d in sorted((self.reg.garden / "pending").iterdir()):
            m = d / "meta.json"
            if m.exists():
                out.append(json.loads(m.read_text()))
        return [p for p in out if p["status"].startswith("PENDING") or p["status"] == "UNVALIDATED"]

    def approve(self, pid: str, actor: str = "user") -> str:
        d = self.reg.garden / "pending" / pid
        prop = Proposal(**json.loads((d / "meta.json").read_text()))
        if self.reg.get(prop.skill) and prop.change_type != "create":
            self.reg.update(prop.skill, description=prop.description or None, body=prop.body or None, purpose=prop.purpose or None, actor="evolve", reason=f"approved {pid}")
        else:
            self.reg.create(prop.skill, prop.family, prop.description, prop.body, prop.purpose, actor="evolve", created_by="evolve")
        prop.status = "ACCEPTED"
        (d / "meta.json").write_text(json.dumps(prop.__dict__, indent=1))
        self._append("skill-impact.md", f"- **{pid} ACCEPTED** by {actor} at {time.strftime('%Y-%m-%d %H:%M')}\n")
        self._append("logs.md", f"## [{time.strftime('%Y-%m-%d %H:%M')}] approve | {pid} | {prop.skill}\n")
        return f"applied {pid} to {prop.skill}"

    def reject(self, pid: str, reason: str = "", actor: str = "user") -> str:
        d = self.reg.garden / "pending" / pid
        prop = Proposal(**json.loads((d / "meta.json").read_text()))
        prop.status = "REJECTED"
        (d / "meta.json").write_text(json.dumps(prop.__dict__, indent=1))
        self._append("skill-impact.md", f"- **{pid} REJECTED** by {actor}: {reason}\n")
        self._append("logs.md", f"## [{time.strftime('%Y-%m-%d %H:%M')}] reject | {pid} | {reason}\n")
        return f"rejected {pid}"

    # ---- one full iteration ------------------------------------------
    def evolve_once(self, target: str | None = None, runner_factory: Callable[[Path], Runner] | None = None, judge_model: str | None = None, since_trace: str | None = None) -> Proposal | None:
        self.maintain(since_trace=since_trace, skill=target)
        prop = self.propose(target)
        if not prop:
            return None
        prop = self.validate(prop, runner_factory, judge_model)
        self.stage(prop)
        return prop
