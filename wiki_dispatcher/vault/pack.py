"""Context packing: turn a set of notes into a budgeted markdown brief the model can consume.

Follows the just-in-time / progressive-disclosure guidance: a catalog of lightweight
identifiers first, then note bodies truncated proportionally to fit the budget, every
excerpt cited by vault path so the agent can `vault_read` the rest on demand.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import Branch
from .index import VaultIndex
from .parse import count_tokens


@dataclass
class Packed:
    text: str
    tokens: int
    included: list[str]
    truncated: list[str]
    omitted: list[str]


def _first_para(body: str, n: int = 240) -> str:
    for para in body.split("\n\n"):
        t = para.strip().lstrip("#").strip()
        if t and not t.startswith(("---", "```", "![[")):
            return (t[:n] + "…") if len(t) > n else t
    return ""


def pack_notes(ix: VaultIndex, paths: list[str], budget: int, reserve_catalog: float = 0.12, reasons: dict[str, str] | None = None) -> Packed:
    """Pack `paths` (already ordered by priority) into <= budget tokens."""
    reasons = reasons or {}
    catalog_lines = ["## Catalog", ""]
    bodies: list[tuple[str, str]] = []
    for p in paths:
        n = ix.get(p)
        if not n:
            continue
        body = ix.read(p)
        why = f" — _{reasons[p]}_" if p in reasons else ""
        catalog_lines.append(f"- `{p}` **{n.title}** ({n.tokens} tok){why}: {_first_para(body)}")
        bodies.append((p, body))
    catalog = "\n".join(catalog_lines)
    catalog_tokens = count_tokens(catalog)
    remaining = max(0, budget - catalog_tokens)

    # Greedy by priority: `paths` is already ordered (seed first, then best-first). High-priority
    # notes land whole; the tail gets truncated, then omitted. Min useful excerpt = 150 tokens.
    included, truncated, omitted, chunks = [], [], [], []
    for p, body in bodies:
        need = count_tokens(body)
        if need <= remaining:
            chunks.append(f"### `{p}`\n\n{body.strip()}\n")
            included.append(p)
            remaining -= need
        elif remaining >= 150:
            ratio = remaining / need
            cut = body[: int(len(body) * ratio)].rsplit("\n", 1)[0]
            chunks.append(f"### `{p}`\n\n{cut}\n\n_[truncated {need - remaining} tokens; `vault_read` for the rest]_\n")
            truncated.append(p)
            remaining = 0
        else:
            omitted.append(p)

    text = catalog + "\n\n## Notes\n\n" + "\n".join(chunks)
    if omitted:
        text += "\n\n## Omitted (over budget)\n\n" + "\n".join(f"- `{p}`" for p in omitted)
    return Packed(text=text, tokens=count_tokens(text), included=included, truncated=truncated, omitted=omitted)


def pack_branch(ix: VaultIndex, br: Branch, budget: int | None = None) -> Packed:
    reasons = {n.path: f"hop {n.hop} via {n.kind} from `{n.via}`" for n in br.nodes if n.hop}
    return pack_notes(ix, br.paths, budget or br.budget, reasons=reasons)
