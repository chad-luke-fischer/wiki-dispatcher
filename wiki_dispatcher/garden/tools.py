"""Agent-facing garden tools: list / view / manage skills, all ledgered.

`garden-tend` (the skill) teaches the agent when to use these; `skill_manage` enforces the
Hermes lesson of read-before-write: a patch is refused unless `skill_view` was called on the
same skill earlier in this process.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .registry import SkillRegistry


def make_garden_tools(reg: SkillRegistry, allow_write: bool = True) -> list:
    viewed: set[str] = set()

    @tool
    def skills_list(include_archived: bool = False) -> str:
        """List every skill in the garden with family, state, usage telemetry, and eval count."""
        return json.dumps([s.summary() for s in reg.all(include_archived=include_archived)], indent=1)

    @tool
    def skill_view(name: str, file: str = "") -> str:
        """View a skill's SKILL.md (default), or a support file such as 'PURPOSE.md', 'references/x.md', 'evals/evals.json'. Required before patching."""
        s = reg.get(name)
        if not s:
            return f"ERROR: no skill named {name}"
        viewed.add(name)
        reg.touch(name, "view")
        p = s.path / (file or "SKILL.md")
        if not p.exists():
            return f"ERROR: {file} not found in {name}"
        return p.read_text()

    @tool
    def skill_lint(name: str = "") -> str:
        """Lint one skill (or all) against garden conventions: naming, description length, PURPOSE.md, negative tool claims, incident-log shape."""
        if name:
            s = reg.get(name)
            return json.dumps(reg.validate(s) if s else [f"no skill {name}"])
        return json.dumps(reg.lint_all(), indent=1)

    @tool
    def skill_manage(action: str, name: str, family: str = "", description: str = "", body: str = "", purpose: str = "", file: str = "", content: str = "", reason: str = "") -> str:
        """Create, patch, archive, restore, pin/unpin a skill, or write a support file.
        action ∈ {create, patch, archive, restore, pin, unpin, write_file}.
        create: family + description + body + purpose required. patch: body and/or description (+reason). write_file: file (under references/|scripts/|assets/|evals/) + content.
        Every mutation is ledgered and reversible. Archiving never deletes."""
        if not allow_write:
            return "ERROR: garden is read-only in this session"
        try:
            if action == "create":
                if not (family and description and body and purpose):
                    return "ERROR: create needs family, description, body, purpose"
                s = reg.create(name, family, description, body, purpose, actor="agent", created_by="agent")
                return f"created {s.name} in {family} (state=seed). Lint: {reg.validate(s) or 'clean'}"
            if action == "patch":
                if name not in viewed:
                    return f"ERROR: read-before-write — call skill_view('{name}') first"
                s = reg.update(name, description=description or None, body=body or None, purpose=purpose or None, actor="agent", reason=reason)
                return f"patched {name} -> v{s.version}. Lint: {reg.validate(s) or 'clean'}"
            if action == "archive":
                return f"archived to {reg.archive(name, actor='agent', reason=reason)}"
            if action == "restore":
                return f"restored to {reg.restore(name, actor='agent')}"
            if action in ("pin", "unpin"):
                reg.update(name, pinned=(action == "pin"), actor="agent", reason=reason)
                return f"{action}ned {name}"
            if action == "write_file":
                return f"wrote {reg.write_file(name, file, content, actor='agent', reason=reason)}"
            return f"ERROR: unknown action {action}"
        except Exception as e:  # surface, don't crash the agent
            return f"ERROR: {type(e).__name__}: {e}"

    @tool
    def garden_index() -> str:
        """Read the garden's pattern-wiki index (PROBLEM + ROOT CAUSE + FIX per pattern) and the skill-impact ledger summary."""
        idx = reg.garden / "wiki" / "index.md"
        impact = reg.garden / "wiki" / "skill-impact.md"
        return (idx.read_text() if idx.exists() else "(no index)") + "\n\n---\n\n" + (impact.read_text()[-4000:] if impact.exists() else "(no impact ledger)")

    tools = [skills_list, skill_view, skill_lint, garden_index]
    if allow_write:
        tools.append(skill_manage)
    return tools
