"""Usage + cost ledger: one JSON line per run in ~/.wiki-dispatcher/usage.jsonl.

Token counts come from LangChain `usage_metadata` on AI messages (provider-reported, includes
cache fields when the provider returns them). Cost is a list-price *estimate* from the config
price table — not billing.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from langchain_core.messages import AIMessage


def sum_usage(messages: list) -> dict[str, dict[str, int]]:
    """Per-model token totals across a result's messages. Dedupes by message id."""
    seen, totals = set(), defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0})
    for m in messages:
        if not isinstance(m, AIMessage) or not m.usage_metadata:
            continue
        if m.id and m.id in seen:
            continue
        seen.add(m.id)
        model = (m.response_metadata or {}).get("model_name") or (m.response_metadata or {}).get("model") or "unknown"
        u = m.usage_metadata
        totals[model]["input"] += u.get("input_tokens", 0)
        totals[model]["output"] += u.get("output_tokens", 0)
        totals[model]["cache_read"] += (u.get("input_token_details") or {}).get("cache_read", 0)
    return dict(totals)


def estimate_cost(totals: dict[str, dict[str, int]], price_table: dict[str, tuple[float, float]]) -> float:
    cost = 0.0
    for model, t in totals.items():
        key = next((k for k in price_table if model in k or k.split(":")[-1] in model), None)
        if not key:
            continue
        pin, pout = price_table[key]
        cost += t["input"] / 1e6 * pin + t["output"] / 1e6 * pout
    return round(cost, 5)


def record_run(log: Path, *, kind: str, vault: str, thread: str, totals: dict, cost: float, tools: list[str], skills: list[str], duration_s: float, note: str = "") -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": kind,  # dispatch | chat | evolve | eval
        "vault": vault,
        "thread": thread,
        "tokens": totals,
        "cost_usd": cost,
        "tools": tools,
        "skills": skills,
        "duration_s": round(duration_s, 1),
        "note": note,
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def summarize(log: Path, since_days: float | None = None) -> dict:
    if not log.exists():
        return {"runs": 0, "cost_usd": 0.0, "by_model": {}, "by_kind": {}}
    cutoff = time.time() - since_days * 86400 if since_days else 0
    runs, cost, by_model, by_kind = 0, 0.0, defaultdict(lambda: {"input": 0, "output": 0}), defaultdict(int)
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if cutoff and time.mktime(time.strptime(e["ts"], "%Y-%m-%dT%H:%M:%S")) < cutoff:
            continue
        runs += 1
        cost += e.get("cost_usd", 0)
        by_kind[e.get("kind", "?")] += 1
        for model, t in e.get("tokens", {}).items():
            by_model[model]["input"] += t.get("input", 0)
            by_model[model]["output"] += t.get("output", 0)
    return {"runs": runs, "cost_usd": round(cost, 4), "by_model": dict(by_model), "by_kind": dict(by_kind)}
