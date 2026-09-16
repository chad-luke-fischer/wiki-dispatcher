"""Graph operations over the index: neighbors, budgeted branch extraction, hubs/MOCs, paths.

Edge weights (from the research synthesis): explicit body link 1.0 > backlink 0.8 >
frontmatter link 0.6 > embed 0.5 > shared tag 0.3. Branch extraction is best-first from the
seed and stops when the cumulative token estimate would exceed the budget.
"""

from __future__ import annotations

import heapq
import math
import re
from dataclasses import dataclass, field

import networkx as nx

from .index import VaultIndex

EDGE_WEIGHT = {"body": 1.0, "mdlink": 1.0, "backlink": 0.8, "frontmatter": 0.6, "embed": 0.5, "tag": 0.3}
HUB_NAME_CUES = re.compile(r"\b(moc|index|map|hub|overview|home|dashboard)\b", re.I)
HUB_TAGS = {"moc", "hub", "index", "map"}


@dataclass
class BranchNode:
    path: str
    hop: int
    score: float
    via: str  # path that led here
    kind: str  # edge kind
    tokens: int


@dataclass
class Branch:
    seed: str
    depth: int
    budget: int
    nodes: list[BranchNode] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # ran out of budget

    @property
    def paths(self) -> list[str]:
        return [n.path for n in self.nodes]

    @property
    def tokens(self) -> int:
        return sum(n.tokens for n in self.nodes)


def _pagerank(g: nx.DiGraph, alpha: float = 0.85, iters: int = 50) -> dict[str, float]:
    """Pure-Python power iteration (avoids the numpy/scipy dependency for small vaults)."""
    n = g.number_of_nodes()
    if n == 0:
        return {}
    pr = {v: 1.0 / n for v in g}
    for _ in range(iters):
        nxt = {v: (1 - alpha) / n for v in g}
        for v in g:
            out = list(g.successors(v))
            if not out:
                for u in g:
                    nxt[u] += alpha * pr[v] / n
                continue
            wsum = sum(g[v][u].get("weight", 1.0) for u in out) or 1.0
            for u in out:
                nxt[u] += alpha * pr[v] * g[v][u].get("weight", 1.0) / wsum
        pr = nxt
    return pr


class VaultGraph:
    def __init__(self, index: VaultIndex):
        self.ix = index
        self.g = nx.DiGraph()
        for n in index.all_notes():
            self.g.add_node(n.path, title=n.title, tokens=n.tokens, mtime=n.mtime, folder=n.folder)
        for r in index.con.execute("SELECT src, dst, kind FROM links WHERE resolved=1"):
            if r["src"] in self.g and r["dst"] in self.g:
                w = EDGE_WEIGHT.get(r["kind"], 0.5)
                if self.g.has_edge(r["src"], r["dst"]):
                    self.g[r["src"]][r["dst"]]["weight"] = max(self.g[r["src"]][r["dst"]]["weight"], w)
                else:
                    self.g.add_edge(r["src"], r["dst"], weight=w, kind=r["kind"])

    # ---- neighborhood ---------------------------------------------------
    def neighbors(self, path: str) -> list[tuple[str, str, float]]:
        """[(neighbor, kind, weight)] over out-links, backlinks, and shared tags."""
        out: dict[str, tuple[str, float]] = {}
        for _, dst, d in self.g.out_edges(path, data=True):
            out[dst] = (d["kind"], d["weight"])
        for src, _, d in self.g.in_edges(path, data=True):
            if src not in out or out[src][1] < EDGE_WEIGHT["backlink"]:
                out[src] = ("backlink", EDGE_WEIGHT["backlink"])
        for tag in self.ix.tags_of(path):
            for p in self.ix.notes_with_tag(tag, prefix=False):
                if p != path and p not in out:
                    out[p] = (f"tag:{tag}", EDGE_WEIGHT["tag"])
        return [(p, k, w) for p, (k, w) in out.items()]

    # ---- branch extraction --------------------------------------------
    def branch(self, seed: str, depth: int = 2, budget: int = 8000, recency_half_life_days: float | None = None) -> Branch:
        """Best-first expansion from `seed`, bounded by hop depth and token budget.

        score(node) = parent_score * edge_weight / hop  (optionally * recency decay).
        The seed is always included. Nodes that would blow the budget are listed in `skipped`.
        """
        seed_path = self.ix.resolve(seed) or seed
        if seed_path not in self.g:
            raise KeyError(f"seed not in vault: {seed}")
        br = Branch(seed=seed_path, depth=depth, budget=budget)
        seed_tokens = self.g.nodes[seed_path]["tokens"]
        br.nodes.append(BranchNode(seed_path, 0, 1.0, seed_path, "seed", seed_tokens))
        used = seed_tokens
        seen = {seed_path}
        heap: list[tuple[float, int, str, str, str]] = []  # (-score, hop, path, via, kind)
        newest = max((d.get("mtime", 0) for _, d in self.g.nodes(data=True)), default=0)

        def push(frontier_path: str, hop: int, parent_score: float):
            for nb, kind, w in self.neighbors(frontier_path):
                if nb in seen:
                    continue
                s = parent_score * w / hop
                if recency_half_life_days:
                    age_days = max(0.0, (newest - self.g.nodes[nb].get("mtime", newest)) / 86400)
                    s *= math.pow(0.5, age_days / recency_half_life_days)
                heapq.heappush(heap, (-s, hop, nb, frontier_path, kind))

        push(seed_path, 1, 1.0)
        while heap:
            neg, hop, p, via, kind = heapq.heappop(heap)
            if p in seen:
                continue
            seen.add(p)
            t = self.g.nodes[p]["tokens"]
            if used + t > budget:
                br.skipped.append(p)
                continue
            used += t
            br.nodes.append(BranchNode(p, hop, -neg, via, kind, t))
            if hop < depth:
                push(p, hop + 1, -neg)
        return br

    # ---- hubs / MOCs ----------------------------------------------------
    def hubs(self, limit: int = 10) -> list[tuple[str, float, dict]]:
        """Score = z(in)*z(out) + name/tag/frontmatter cues + link density. Returns top `limit`."""
        if not self.g:
            return []
        pr = _pagerank(self.g)
        rows = []
        for n, d in self.g.nodes(data=True):
            indeg, outdeg = self.g.in_degree(n), self.g.out_degree(n)
            words = max(1, d["tokens"])
            density = outdeg / (words / 100)
            cues = 0.0
            if HUB_NAME_CUES.search(d["title"]) or HUB_NAME_CUES.search(n):
                cues += 1.0
            note = self.ix.get(n)
            if note and str(note.frontmatter.get("type", "")).lower() in HUB_TAGS:
                cues += 1.5
            if HUB_TAGS & set(self.ix.tags_of(n)):
                cues += 1.0
            score = math.log1p(indeg) * math.log1p(outdeg) + cues + min(density, 3) * 0.3 + pr[n] * 10
            rows.append((n, round(score, 3), {"in": indeg, "out": outdeg, "pagerank": round(pr[n], 4), "cues": cues}))
        rows.sort(key=lambda r: -r[1])
        return rows[:limit]

    # ---- paths ----------------------------------------------------------
    def paths(self, a: str, b: str, k: int = 3, cutoff: int = 5) -> list[list[str]]:
        a, b = self.ix.resolve(a) or a, self.ix.resolve(b) or b
        ug = self.g.to_undirected(as_view=True)
        try:
            gen = nx.shortest_simple_paths(ug, a, b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        out = []
        for p in gen:
            if len(p) - 1 > cutoff or len(out) >= k:
                break
            out.append(p)
        return out

    def centrality(self, limit: int = 20) -> list[tuple[str, float]]:
        bc = nx.betweenness_centrality(self.g, weight=None) if self.g.number_of_edges() else {}
        return sorted(bc.items(), key=lambda kv: -kv[1])[:limit]

    def to_mermaid(self, paths: list[str]) -> str:
        sub = self.g.subgraph(paths)
        lines = ["graph LR"]
        ids = {p: f"n{i}" for i, p in enumerate(sub.nodes)}
        for p in sub.nodes:
            lines.append(f'  {ids[p]}["{sub.nodes[p]["title"]}"]')
        for s, d in sub.edges:
            lines.append(f"  {ids[s]} --> {ids[d]}")
        return "\n".join(lines)
