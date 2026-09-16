"""Thin model-agnostic LLM helper for the non-agent parts (wiki maintainer, proposer, judges).

Everything goes through LangChain's `init_chat_model("provider:model")`, so swapping providers
is a config change. JSON extraction is defensive: models wrap JSON in fences or prose.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def get_model(spec: str, **kwargs):
    from langchain.chat_models import init_chat_model

    return init_chat_model(spec, **kwargs)


def complete(spec: str, system: str, user: str, temperature: float = 0.2) -> tuple[str, dict]:
    """Returns (text, usage_metadata)."""
    m = get_model(spec, temperature=temperature)
    resp: AIMessage = m.invoke([("system", system), ("user", user)])
    text = resp.content if isinstance(resp.content, str) else "".join(
        c.get("text", "") for c in resp.content if isinstance(c, dict)
    )
    return text, dict(resp.usage_metadata or {})


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model reply."""
    m = _FENCE.search(text)
    candidate = m.group(1) if m else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # last resort: first {...} or [...] span
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = candidate.find(opener), candidate.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(candidate[i : j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON found in model reply")
