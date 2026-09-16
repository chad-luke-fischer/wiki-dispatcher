from wiki_dispatcher.vault.graph import VaultGraph
from wiki_dispatcher.vault.pack import pack_branch, pack_notes


def test_index_counts_and_links(ix):
    assert ix.count() == 16
    assert ix.resolve("Hermes") == "wiki/entities/Hermes Agent.md"  # alias
    assert ix.resolve("index") == "wiki/index.md"  # shortest path wins
    assert ("daily/2026-09-12.md", "Nonexistent Note") in ix.broken_links()
    assert "wiki/concepts/Orphan Idea.md" in ix.orphans()


def test_frontmatter_links_and_tags(ix):
    outs = dict(ix.outlinks("wiki/concepts/Context Engineering.md"))
    assert outs["wiki/index.md"] == "frontmatter"  # up: "[[index]]"
    assert "agents/context" in ix.tags_of("wiki/concepts/Context Engineering.md")
    assert "wiki/concepts/Context Engineering.md" in ix.notes_with_tag("agents")  # namespace prefix


def test_search(ix):
    hits = [p for p, _, _ in ix.search("curator")]
    assert "wiki/entities/Hermes Agent.md" in hits


def test_incremental_build(ix, vault):
    assert ix.build()["indexed"] == 0
    (vault / "wiki" / "concepts" / "New.md").write_text("# New\n\nLinks to [[Skill Evolution]].\n")
    stats = ix.build()
    assert stats["indexed"] == 1 and stats["total"] == 17
    assert ("wiki/concepts/New.md", "body") in ix.backlinks("wiki/concepts/Skill Evolution.md")


def test_hubs_and_branch(ix):
    g = VaultGraph(ix)
    assert g.hubs(1)[0][0] == "wiki/index.md"
    br = g.branch("Skill Evolution", depth=2, budget=1500)
    assert br.nodes[0].path == "wiki/concepts/Skill Evolution.md"
    assert br.tokens <= 1500
    kinds = {n.kind for n in br.nodes}
    assert "body" in kinds and "backlink" in kinds
    hop1 = [n.path for n in br.nodes if n.hop == 1]
    assert "wiki/entities/WikiSkill.md" in hop1


def test_branch_respects_budget(ix):
    g = VaultGraph(ix)
    br = g.branch("Skill Evolution", depth=2, budget=250)
    assert br.tokens <= 250 and br.skipped


def test_paths(ix):
    g = VaultGraph(ix)
    ps = g.paths("Obsidian", "Hermes")
    assert ps and ps[0][0] == "wiki/entities/Obsidian.md" and ps[0][-1] == "wiki/entities/Hermes Agent.md"


def test_pack(ix):
    g = VaultGraph(ix)
    br = g.branch("Skill Evolution", depth=1, budget=2000)
    pk = pack_branch(ix, br)
    assert pk.tokens <= 2000 + 50  # catalog estimate slack
    assert "## Catalog" in pk.text and "## Notes" in pk.text
    assert pk.included[0] == "wiki/concepts/Skill Evolution.md"
    small = pack_notes(ix, br.paths, budget=400)
    assert small.omitted or small.truncated
