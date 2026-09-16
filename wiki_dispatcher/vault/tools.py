"""LangChain tools that expose the vault layer to the agent.

Skills teach *when* and *how* to compose these; the tools do the deterministic work.
All tools are read-only against the vault. Names are stable — skills reference them.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .graph import VaultGraph
from .index import VaultIndex
from .pack import pack_branch, pack_notes


def make_vault_tools(ix: VaultIndex, default_budget: int = 8000, default_depth: int = 2) -> list:
    graph_cache: dict[str, VaultGraph] = {}

    def graph() -> VaultGraph:
        if "g" not in graph_cache:
            graph_cache["g"] = VaultGraph(ix)
        return graph_cache["g"]

    @tool
    def vault_map() -> str:
        """Orient in the vault: note count, folder census, top tags, hub/MOC candidates, orphans, broken links. Call first on any new task."""
        g = graph()
        hubs = g.hubs(8)
        return json.dumps(
            {
                "notes": ix.count(),
                "folders": ix.folder_census()[:15],
                "top_tags": ix.tag_census()[:20],
                "hubs": [{"path": p, "score": s, **m} for p, s, m in hubs],
                "orphans": ix.orphans()[:20],
                "broken_links": ix.broken_links()[:20],
            },
            indent=1,
        )

    @tool
    def vault_search(query: str, limit: int = 10) -> str:
        """Full-text (BM25) search over note titles and bodies. Returns path, snippet, score. Use FTS5 syntax: quotes for phrases, OR, prefix*."""
        return json.dumps([{"path": p, "snippet": s, "score": round(sc, 3)} for p, s, sc in ix.search(query, limit)], indent=1)

    @tool
    def vault_read(path: str, max_chars: int = 20000) -> str:
        """Read a note by vault path or by [[name]]. Returns frontmatter + body (truncated at max_chars)."""
        n = ix.get(path)
        if not n:
            return f"ERROR: not found: {path}"
        body = ix.read(n.path)
        head = f"<!-- {n.path} | tags: {', '.join(ix.tags_of(n.path))} | tokens: {n.tokens} -->\n"
        return head + (body[:max_chars] + ("\n…[truncated]" if len(body) > max_chars else ""))

    @tool
    def vault_neighbors(path: str) -> str:
        """Immediate neighborhood of a note: out-links, backlinks, and shared-tag siblings with edge kinds and weights."""
        p = ix.resolve(path) or path
        return json.dumps([{"path": q, "kind": k, "weight": w} for q, k, w in graph().neighbors(p)], indent=1)

    @tool
    def vault_backlinks(path: str) -> str:
        """Who references this note? Returns [(source_path, link_kind)]."""
        p = ix.resolve(path) or path
        return json.dumps(ix.backlinks(p))

    @tool
    def vault_branch(seed: str, depth: int = default_depth, budget: int = default_budget, pack: bool = True) -> str:
        """Extract a budgeted branch of the vault around a seed note (best-first over links/backlinks/tags, depth-bounded). With pack=True returns a ready-to-use markdown brief with catalog + cited excerpts; otherwise the node list."""
        try:
            br = graph().branch(seed, depth=depth, budget=budget)
        except KeyError as e:
            return f"ERROR: {e}"
        if not pack:
            return json.dumps([n.__dict__ for n in br.nodes] + [{"skipped": br.skipped}], indent=1)
        packed = pack_branch(ix, br)
        return packed.text

    @tool
    def vault_hubs(limit: int = 10) -> str:
        """Find hub / MOC (map-of-content) notes by degree, PageRank, and naming/frontmatter cues."""
        return json.dumps([{"path": p, "score": s, **m} for p, s, m in graph().hubs(limit)], indent=1)

    @tool
    def vault_paths(a: str, b: str, k: int = 3) -> str:
        """Shortest link paths between two notes (undirected), up to k paths. Useful to bridge two ideas."""
        return json.dumps(graph().paths(a, b, k=k), indent=1)

    @tool
    def vault_tag(tag: str, limit: int = 50) -> str:
        """Notes carrying a tag or any nested tag under it (e.g. 'project' matches 'project/glu')."""
        return json.dumps(ix.notes_with_tag(tag)[:limit])

    @tool
    def vault_frontmatter(key: str, value: str = "") -> str:
        """Notes whose frontmatter has `key` (optionally equal to `value`). E.g. key='type', value='concept'."""
        return json.dumps(ix.frontmatter_query(key, value or None))

    @tool
    def vault_pack(paths: list[str], budget: int = default_budget) -> str:
        """Pack an explicit list of note paths (highest priority first) into a budgeted markdown brief with citations."""
        return pack_notes(ix, paths, budget).text

    @tool
    def vault_mermaid(paths: list[str]) -> str:
        """Render the link subgraph among the given note paths as a Mermaid diagram."""
        return graph().to_mermaid([ix.resolve(p) or p for p in paths])

    return [
        vault_map,
        vault_search,
        vault_read,
        vault_neighbors,
        vault_backlinks,
        vault_branch,
        vault_hubs,
        vault_paths,
        vault_tag,
        vault_frontmatter,
        vault_pack,
        vault_mermaid,
    ]
