import json

import frontmatter

from wiki_dispatcher.deliver import infer_kind, write_deliverable


def test_infer_kind():
    assert infer_kind("make me a slide deck on X") == "marp"
    assert infer_kind("export the concepts as csv") == "dataset"
    assert infer_kind("compare Hermes and WikiSkill in a table") == "table"
    assert infer_kind("what is context engineering?") == "note"
    assert infer_kind("give me a brief on X") == "brief"
    assert infer_kind("lay this out on a canvas") == "canvas"


def test_write_markdown_deliverable(tmp_path):
    p = write_deliverable(tmp_path, "brief", "brief on Skill Evolution", "# X\n\nSee [[Skill Evolution]] and [[Hermes Agent|Hermes]].\n", "t1")
    post = frontmatter.load(p)
    assert p.suffix == ".md" and post["kind"] == "brief" and post["trace"] == "t1"
    assert post["sources"] == ["[[Skill Evolution]]", "[[Hermes Agent]]"]
    assert "dispatch/brief" in post["tags"]


def test_write_canvas_and_dataset(tmp_path):
    canvas = '```json\n{"nodes":[{"id":"a","type":"text","text":"hi","x":0,"y":0,"width":100,"height":50}],"edges":[]}\n```'
    p = write_deliverable(tmp_path, "canvas", "canvas of X", canvas, "t2")
    assert p.suffix == ".canvas" and json.loads(p.read_text())["nodes"][0]["id"] == "a"
    p = write_deliverable(tmp_path, "dataset", "csv of concepts", "caption\n```csv\nname,type\nA,concept\n```", "t3")
    assert p.suffix == ".csv" and p.read_text().startswith("name,type")
