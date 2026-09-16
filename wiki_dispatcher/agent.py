"""Agent factory: a deep agent mounted to the vault, with the garden's skills and tools.

Backend routes (virtual paths the model sees):
    /vault/   → the Obsidian vault (read-only; deliverables never land here directly)
    /skills/  → skills/<family>/<name>/SKILL.md (read-only to the model; CRUD goes via skill_manage)
    /garden/  → the pattern wiki (read-only to the model; the evolve loop writes it)
    /out/     → deliverables directory (writable)

Model tiers come from config; any `init_chat_model` string works ("anthropic:…", "openai:…",
"ollama:…", "openrouter:…").
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.backends.filesystem import FilesystemBackend

from .config import REPO_ROOT, Config
from .deliver.router import kind_instructions
from .garden.registry import SkillRegistry
from .garden.tools import make_garden_tools
from .trace import TraceWriter, extract_tool_calls, final_text, skills_used
from .usage import estimate_cost, record_run, sum_usage
from .vault.index import VaultIndex
from .vault.tools import make_vault_tools

AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _checkpointer(cfg: Config):
    """SQLite if langgraph-checkpoint-sqlite is installed, else in-memory for the process."""
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        cfg.sessions_dir.mkdir(parents=True, exist_ok=True)
        return SqliteSaver(sqlite3.connect(cfg.sessions_dir / "checkpoints.db", check_same_thread=False))
    except Exception:
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()


def system_prompt(cfg: Config, kind: str | None = None) -> str:
    parts = [AGENTS_MD.read_text() if AGENTS_MD.exists() else "You are wiki-dispatcher."]
    if cfg.vault:
        for schema in ("CLAUDE.md", "AGENTS.md", "README.md"):
            p = cfg.vault / schema
            if p.exists():
                parts.append(f"\n\n# The mounted vault's own schema ({schema})\n\n{p.read_text()[:6000]}")
                break
        parts.append(f"\n\nVault name: {cfg.vault.name}. Context budget per pack: {cfg.context_budget_tokens} tokens. Default traversal depth: {cfg.default_depth}.")
    if kind:
        parts.append(f"\n\n# Deliverable contract for this task\nKind: **{kind}**. {kind_instructions(kind)}")
    return "".join(parts)


@dataclass
class Dispatcher:
    cfg: Config
    ix: VaultIndex
    reg: SkillRegistry
    agent: object
    traces: TraceWriter
    thread: str

    def run(self, message: str, kind: str | None = None, note: str = "") -> dict:
        """One turn. Returns {"text", "messages", "trace_id", "totals", "cost"}."""
        t0 = time.time()
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": self.thread}, "recursion_limit": 200},
        )
        messages = result["messages"]
        totals = sum_usage(messages)
        cost = estimate_cost(totals, self.cfg.price_table)
        calls = extract_tool_calls(messages)
        used = skills_used(calls)
        for s in used:
            self.reg.touch(s, "use")
        trace_id = self.traces.write(kind=kind or "chat", vault=self.cfg.vault_slug, message=message, messages=messages, totals=totals, cost=cost, extra={"thread": self.thread})
        record_run(self.cfg.usage_log, kind=kind or "chat", vault=self.cfg.vault_slug, thread=self.thread, totals=totals, cost=cost, tools=[c["tool"] for c in calls], skills=used, duration_s=time.time() - t0, note=note)
        return {"text": final_text(messages), "messages": messages, "trace_id": trace_id, "totals": totals, "cost": cost, "skills": used}


def build_dispatcher(cfg: Config, *, skills_root: Path | None = None, model: str | None = None, kind: str | None = None, thread: str | None = None, garden_write: bool = True, with_subagents: bool = True) -> Dispatcher:
    if not cfg.vault:
        raise SystemExit("no vault mounted: run `wd mount <path>` or pass --vault")
    cfg.ensure_dirs()
    ix = VaultIndex(cfg.vault, cfg.index_db)
    ix.build()
    skills_root = skills_root or cfg.skills_root
    reg = SkillRegistry(skills_root, cfg.garden_root)
    cfg.deliverables.mkdir(parents=True, exist_ok=True)

    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/vault/": FilesystemBackend(root_dir=cfg.vault, virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=skills_root, virtual_mode=True),
            "/garden/": FilesystemBackend(root_dir=cfg.garden_root, virtual_mode=True),
            "/out/": FilesystemBackend(root_dir=cfg.deliverables, virtual_mode=True),
        },
    )
    permissions = [
        FilesystemPermission(operations=["write"], paths=["/vault/**"], mode="interrupt" if cfg.write_vault else "deny"),
        FilesystemPermission(operations=["write"], paths=["/skills/**", "/garden/**"], mode="deny"),
        FilesystemPermission(operations=["read"], paths=["/vault/.obsidian/**"], mode="deny"),
    ]
    tools = make_vault_tools(ix, cfg.context_budget_tokens, cfg.default_depth) + make_garden_tools(reg, allow_write=garden_write)

    subagents = []
    if with_subagents:
        subagents.append(
            {
                "name": "traverser",
                "description": "Read-only vault explorer. Give it a seed note or question; it returns a budgeted, cited context pack. Use for parallel branch extraction on big asks.",
                "system_prompt": "You explore an Obsidian vault with the vault_* tools and the traverse skills. Return ONLY a cited context pack (vault_branch / vault_pack output plus a 3-line synthesis). Never write files.",
                "tools": make_vault_tools(ix, cfg.context_budget_tokens, cfg.default_depth),
                "skills": ["/skills/traverse/"],
                "model": cfg.models.worker,
                "permissions": [FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")],
            }
        )

    agent = create_deep_agent(
        model=model or cfg.models.frontier,
        tools=tools,
        system_prompt=system_prompt(cfg, kind),
        skills=reg.family_dirs(),
        backend=backend,
        permissions=permissions,
        subagents=subagents or None,
        checkpointer=_checkpointer(cfg),
        name="wiki-dispatcher",
    )
    return Dispatcher(cfg=cfg, ix=ix, reg=reg, agent=agent, traces=TraceWriter(cfg.traces_dir), thread=thread or time.strftime("%Y%m%d-%H%M%S"))


def eval_runner_factory(cfg: Config, model: str | None = None):
    """For garden.evolve: returns runner_factory(skills_root) -> runner(prompt) -> {"messages"}."""

    def factory(skills_root: Path):
        d = build_dispatcher(cfg, skills_root=skills_root, model=model or cfg.models.worker, thread=f"eval-{time.time_ns()}", garden_write=False, with_subagents=False)

        def runner(prompt: str) -> dict:
            out = d.run(prompt, kind="eval")
            return {"messages": out["messages"]}

        return runner

    return factory
