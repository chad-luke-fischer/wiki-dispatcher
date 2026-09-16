
import pytest

from wiki_dispatcher.garden.evals import grade
from wiki_dispatcher.garden.evolve import Garden
from wiki_dispatcher.garden.registry import SkillRegistry
from wiki_dispatcher.trace import TraceWriter


def test_registry_discovers_seed_skills(skills_copy, garden_dir):
    reg = SkillRegistry(skills_copy, garden_dir)
    names = {s.name for s in reg.all()}
    assert {"branch-extract", "garden-tend", "deliver-brief", "wiki-lint"} <= names
    assert reg.family_dirs() == ["/skills/traverse/", "/skills/garden/", "/skills/deliver/", "/skills/wiki/"]
    assert reg.lint_all() == {}  # seed skills are clean
    assert reg.get("garden-tend").pinned


def test_crud_is_ledgered(skills_copy, garden_dir):
    reg = SkillRegistry(skills_copy, garden_dir)
    s = reg.create("date-lens", "traverse", "Slice by date.", "# date-lens\n\nSteps.", "Because dates.", actor="cli")
    assert s.state == "seed" and s.version == "0.1.0"
    s = reg.update("date-lens", body="# date-lens\n\nBetter steps.", actor="agent", reason="tighten")
    assert s.version == "0.1.1" and s.usage["patch_count"] == 1
    reg.touch("date-lens", "use")
    assert reg.get("date-lens").usage["reuse_after_patch"] is True
    with pytest.raises(PermissionError):
        reg.archive("garden-tend")
    dest = reg.archive("date-lens", reason="test")
    assert dest.exists() and reg.get("date-lens").state == "archived"
    reg.restore("date-lens")
    assert reg.get("date-lens").state == "active" and (skills_copy / "traverse" / "date-lens").exists()
    actions = [e["action"] for e in reg.ledger.entries("date-lens")]
    assert actions[0] == "create" and "archive" in actions and "restore" in actions


def test_validate_flags_bad_skills(skills_copy, garden_dir):
    reg = SkillRegistry(skills_copy, garden_dir)
    reg.create("bad-one", "wiki", "x", "# bad\n\nThe browser tool does not work. See PR-1 PR-2 PR-3 #4567.", "p")
    problems = reg.validate(reg.get("bad-one"))
    assert any("negative tool claim" in p for p in problems)
    assert any("incident-log" in p for p in problems)


def test_grade_assertions():
    from langchain_core.messages import AIMessage, ToolMessage

    msgs = [
        AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"file_path": "/skills/traverse/branch-extract/SKILL.md"}, "id": "1"}]),
        ToolMessage(content="...", tool_call_id="1"),
        AIMessage(content="", tool_calls=[{"name": "vault_branch", "args": {"seed": "x"}, "id": "2"}]),
        ToolMessage(content="...", tool_call_id="2"),
        AIMessage(content="WikiSkill links [[Hermes Agent]]. Sources: [[WikiSkill]]"),
    ]
    case = {"id": "c", "assertions": [{"type": "contains", "value": "wikiskill"}, {"type": "tool_used", "value": "vault_branch"}, {"type": "skill_used", "value": "branch-extract"}, {"type": "regex", "value": "\\[\\[.+\\]\\]"}, {"type": "max_tool_calls", "value": "1"}]}
    r = grade(case, msgs)
    assert r.passed == 4 and r.total == 5


def test_evolve_loop_stages_and_approves(skills_copy, garden_dir):
    reg = SkillRegistry(skills_copy, garden_dir)
    tw = TraceWriter(garden_dir / "raw" / "traces")
    tid = tw.write(kind="dispatch", vault="fx", message="brief on X", messages=[], totals={}, cost=0.0)
    tw.rate(tid, 2)

    def maintainer(system, user):
        assert tid in user
        return {"patterns": [{"name": "over-deep-branch", "problem": "Branch pulled 40 tag siblings", "root_cause": "depth 3 with tag edges", "fix": "cap depth 2; second seed", "trigger": "broad ask", "rule": "Prefer a second seed over depth 3.", "anti_pattern": "depth=3", "evidence": [tid], "skills": ["branch-extract"]}], "log": "one pattern"}

    def proposer(system, user):
        assert "over-deep-branch" in user and "SKILL-IMPACT" in user
        return {"skill": "branch-extract", "family": "traverse", "change_type": "patch", "rationale": "see over-deep-branch", "patterns": ["over-deep-branch"], "description": reg.get("branch-extract").description, "skill_md_body": reg.get("branch-extract").body() + "\n- Never use depth 3.\n", "purpose_md": "updated"}

    g = Garden(reg, tw, maintainer=maintainer, proposer=proposer)
    prop = g.evolve_once(target="branch-extract", runner_factory=None)
    assert prop.status == "UNVALIDATED"
    assert (garden_dir / "wiki" / "patterns" / "over-deep-branch.md").exists()
    assert "over-deep-branch" in (garden_dir / "wiki" / "index.md").read_text()
    pend = garden_dir / "pending" / prop.id
    assert (pend / "diff.patch").read_text().count("+- Never use depth 3.") == 1
    assert [p["id"] for p in g.pending()] == [prop.id]
    g.approve(prop.id)
    assert "Never use depth 3." in reg.get("branch-extract").body()
    assert reg.get("branch-extract").version == "0.1.1"
    assert "ACCEPTED" in (garden_dir / "wiki" / "skill-impact.md").read_text()
    assert g.pending() == []


def test_evolve_validation_gate_uses_copies(skills_copy, garden_dir):
    reg = SkillRegistry(skills_copy, garden_dir)
    tw = TraceWriter(garden_dir / "raw" / "traces")
    seen_roots = []

    def factory(root):
        seen_roots.append(root)
        body = (root / "traverse" / "branch-extract" / "SKILL.md").read_text()
        # candidate contains the magic word → runner "answers" better
        def runner(prompt):
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(content="WikiSkill Hermes [[x]]" if "MAGIC" in body else "nothing")]}
        return runner

    g = Garden(reg, tw, maintainer=lambda s, u: {"patterns": []}, proposer=lambda s, u: {"skill": "branch-extract", "change_type": "patch", "rationale": "r", "patterns": [], "description": "d", "skill_md_body": "# b\n\nMAGIC", "purpose_md": "p"})
    prop = g.evolve_once(target="branch-extract", runner_factory=factory)
    assert len(seen_roots) == 2 and seen_roots[0] == skills_copy and seen_roots[1] != skills_copy
    assert prop.candidate > prop.baseline and prop.status == "PENDING"
    assert "MAGIC" not in reg.get("branch-extract").body()  # not applied until approved
    g.reject(prop.id, "not convinced")
    assert "REJECTED" in (garden_dir / "wiki" / "skill-impact.md").read_text()
