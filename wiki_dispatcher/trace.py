"""Execution traces: the raw/ layer of the garden wiki. Record everything.

One JSONL file per run under garden/raw/traces/. Traces are immutable inputs to the
evolve loop (WikiSkill's τ). A trace records the message, every tool call, which skills were
read, the final answer, token usage, and an optional human rating (1-5) added later via
`wd rate <trace-id> <n>`.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

SKILL_PATH_RE = re.compile(r"/skills/(?P<family>[^/]+)/(?P<name>[^/]+)/SKILL\.md")


def extract_tool_calls(messages: list) -> list[dict]:
    calls = []
    results = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                res = results.get(tc["id"])
                out = res.content if res else None
                if isinstance(out, list):
                    out = json.dumps(out)
                calls.append(
                    {
                        "tool": tc["name"],
                        "args": tc.get("args", {}),
                        "result_head": (str(out)[:400] if out is not None else None),
                        "error": bool(res and getattr(res, "status", "") == "error"),
                    }
                )
    return calls


def skills_used(calls: list[dict]) -> list[str]:
    names = []
    for c in calls:
        path = str(c.get("args", {}).get("file_path") or c.get("args", {}).get("path") or "")
        if m := SKILL_PATH_RE.search(path):
            if m.group("name") not in names:
                names.append(m.group("name"))
    return names


def final_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not m.tool_calls:
            if isinstance(m.content, str):
                return m.content
            return "".join(c.get("text", "") for c in m.content if isinstance(c, dict))
    return ""


class TraceWriter:
    def __init__(self, traces_dir: Path):
        self.dir = Path(traces_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, *, kind: str, vault: str, message: str, messages: list, totals: dict, cost: float, deliverable: str | None = None, error: str | None = None, extra: dict | None = None) -> str:
        calls = extract_tool_calls(messages)
        tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        rec = {
            "id": tid,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "kind": kind,
            "vault": vault,
            "message": message,
            "tool_calls": calls,
            "skills_used": skills_used(calls),
            "final": final_text(messages)[:8000],
            "deliverable": deliverable,
            "tokens": totals,
            "cost_usd": cost,
            "error": error,
            "rating": None,
            "outcome": "error" if error else "unrated",
            **(extra or {}),
        }
        (self.dir / f"{tid}.jsonl").write_text(json.dumps(rec) + "\n")
        return tid

    def rate(self, trace_id: str, rating: int, note: str = "") -> dict:
        p = self.dir / f"{trace_id}.jsonl"
        rec = json.loads(p.read_text().splitlines()[0])
        rec["rating"] = rating
        rec["outcome"] = "pass" if rating >= 4 else ("fail" if rating <= 2 else "mixed")
        if note:
            rec["rating_note"] = note
        p.write_text(json.dumps(rec) + "\n")
        return rec

    def load(self, trace_id: str) -> dict:
        return json.loads((self.dir / f"{trace_id}.jsonl").read_text().splitlines()[0])

    def all(self) -> list[dict]:
        out = []
        for p in sorted(self.dir.glob("*.jsonl")):
            try:
                out.append(json.loads(p.read_text().splitlines()[0]))
            except Exception:
                continue
        return out

    def sample(self, max_fail: int = 5, max_pass: int = 3, since_trace: str | None = None, skill: str | None = None) -> list[dict]:
        """WikiSkill sampling: ≤5 failing, ≤3 passing, most recent first, each capped at 15k chars."""
        rows = [r for r in self.all() if (not since_trace or r["id"] > since_trace)]
        if skill:
            # prefer traces that used the target skill; fall back to all traces if none are attributed
            attributed = [r for r in rows if skill in r.get("skills_used", [])]
            rows = attributed or rows
        fails = [r for r in rows if r["outcome"] in ("fail", "error")][-max_fail:]
        passes = [r for r in rows if r["outcome"] == "pass"][-max_pass:]
        out = []
        for r in fails + passes:
            s = json.dumps(r)
            out.append(json.loads(s) if len(s) <= 15000 else {**r, "tool_calls": r["tool_calls"][:12], "final": r["final"][:3000], "_truncated": True})
        return out
