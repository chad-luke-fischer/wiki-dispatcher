"""Skill evals: small, cheap, deterministic-first.

skills/<family>/<name>/evals/evals.json:
[
  {"id": "branch-basic",
   "prompt": "Give me a brief on Skill Evolution and what it links to.",
   "expected": "Mentions WikiSkill, Hermes, and the validation gate; cites vault paths.",
   "assertions": [
     {"type": "contains", "value": "WikiSkill"},
     {"type": "regex", "value": "wiki/concepts/.*\\.md"},
     {"type": "tool_used", "value": "vault_branch"},
     {"type": "skill_used", "value": "branch-extract"},
     {"type": "llm_rubric", "value": "Answer cites at least two vault notes and states the validation gate."}
   ]}
]

Score per case = fraction of assertions passed; skill score = mean over cases. The gate in
evolve.py accepts a proposal only if the candidate's score strictly beats the baseline.
`llm_rubric` uses the `cheap` model as judge (0/1). Everything else is free.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..trace import extract_tool_calls, final_text, skills_used

Runner = Callable[[str], dict]  # prompt -> {"messages": [...]}


@dataclass
class CaseResult:
    id: str
    passed: int
    total: int
    details: list[dict] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass
class EvalReport:
    skill: str
    cases: list[CaseResult]

    @property
    def score(self) -> float:
        return sum(c.score for c in self.cases) / len(self.cases) if self.cases else 0.0

    def to_dict(self) -> dict:
        return {"skill": self.skill, "score": round(self.score, 3), "cases": [{"id": c.id, "score": round(c.score, 3), "seconds": c.seconds, "details": c.details} for c in self.cases]}


def _judge(rubric: str, answer: str, judge_model: str | None) -> tuple[bool, str]:
    if not judge_model:
        return False, "no judge model configured"
    from ..llm import complete, extract_json

    text, _ = complete(
        judge_model,
        "You are a strict grader. Reply with JSON {\"pass\": true|false, \"why\": \"...\"} only.",
        f"RUBRIC:\n{rubric}\n\nANSWER:\n{answer[:6000]}",
        temperature=0.0,
    )
    try:
        j = extract_json(text)
        return bool(j.get("pass")), str(j.get("why", ""))
    except Exception:
        return False, "judge reply unparseable"


def grade(case: dict, messages: list, judge_model: str | None = None) -> CaseResult:
    answer = final_text(messages)
    calls = extract_tool_calls(messages)
    tools = [c["tool"] for c in calls]
    skills = skills_used(calls)
    res = CaseResult(id=case["id"], passed=0, total=len(case.get("assertions", [])))
    for a in case.get("assertions", []):
        t, v = a["type"], a.get("value", "")
        ok, why = False, ""
        if t == "contains":
            ok = v.lower() in answer.lower()
        elif t == "not_contains":
            ok = v.lower() not in answer.lower()
        elif t == "regex":
            ok = re.search(v, answer, re.I | re.S) is not None
        elif t == "tool_used":
            ok = v in tools
        elif t == "skill_used":
            ok = v in skills
        elif t == "max_tool_calls":
            ok = len(calls) <= int(v)
        elif t == "llm_rubric":
            ok, why = _judge(v, answer, judge_model)
        else:
            why = f"unknown assertion type {t}"
        res.passed += int(ok)
        res.details.append({"type": t, "value": v, "pass": ok, "why": why})
    return res


def run_evals(skill_name: str, cases: list[dict], runner: Runner, judge_model: str | None = None, only: list[str] | None = None) -> EvalReport:
    results = []
    for case in cases:
        if only and case["id"] not in only:
            continue
        t0 = time.time()
        try:
            out = runner(case["prompt"])
            msgs = out.get("messages", [])
        except Exception as e:  # count a crash as a full fail but keep going
            msgs = []
            cr = CaseResult(id=case["id"], passed=0, total=len(case.get("assertions", [])) or 1, details=[{"type": "run", "pass": False, "why": f"{type(e).__name__}: {e}"}])
            cr.seconds = round(time.time() - t0, 1)
            results.append(cr)
            continue
        cr = grade(case, msgs, judge_model)
        cr.seconds = round(time.time() - t0, 1)
        results.append(cr)
    return EvalReport(skill=skill_name, cases=results)


def load_cases(skill_dir: Path) -> list[dict]:
    p = skill_dir / "evals" / "evals.json"
    return json.loads(p.read_text()) if p.exists() else []
