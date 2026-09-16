"""`wd` — the wiki-dispatcher CLI.

    wd init | mount <vault> | index
    wd vault  map|search|read|branch|hubs|paths|tag|orphans|broken
    wd ask "message" [--as kind] [--out dir]     one-shot dispatch → deliverable
    wd chat                                      REPL (same thread, same vault)
    wd skills list|show|add|update|archive|restore|pin|unpin|lint|ledger
    wd garden status|evolve|pending|approve|reject|eval|sweep|rate
    wd usage [--days N]
    wd fixture <dest>
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from . import __version__
from .config import Config, load_config, write_default_config

app = typer.Typer(help="wiki-dispatcher: a CLI agent mounted to an llm-wiki style Obsidian vault.", no_args_is_help=True)
vault_app = typer.Typer(help="Deterministic vault operations (no LLM).", no_args_is_help=True)
skills_app = typer.Typer(help="Manage the skill garden.", no_args_is_help=True)
garden_app = typer.Typer(help="Evolve, evaluate, and curate skills.", no_args_is_help=True)
app.add_typer(vault_app, name="vault")
app.add_typer(skills_app, name="skills")
app.add_typer(garden_app, name="garden")
con = Console()

VaultOpt = typer.Option(None, "--vault", "-v", help="Vault path (overrides config / WD_VAULT)")


def _cfg(vault: Optional[Path]) -> Config:
    return load_config(vault)


def _index(cfg: Config, rebuild: bool = False):
    from .vault.index import VaultIndex

    if not cfg.vault:
        raise typer.BadParameter("no vault mounted: `wd mount <path>` or --vault")
    cfg.ensure_dirs()
    ix = VaultIndex(cfg.vault, cfg.index_db)
    ix.build(rebuild=rebuild)
    return ix


def _registry(cfg: Config):
    from .garden.registry import SkillRegistry

    return SkillRegistry(cfg.skills_root, cfg.garden_root)


def _garden(cfg: Config):
    from .garden.evolve import Garden
    from .trace import TraceWriter

    return Garden(_registry(cfg), TraceWriter(cfg.traces_dir), models=cfg.models.__dict__)


def _llm_guard(fn):
    """Turn provider/auth failures into one readable line instead of a traceback."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except (typer.Exit, KeyboardInterrupt):
            raise
        except Exception as e:  # noqa: BLE001
            con.print(f"[red]{type(e).__name__}[/]: {str(e)[:400]}")
            con.print("[dim]hint: set the provider API key (ANTHROPIC_API_KEY / OPENAI_API_KEY …) or change \\[models] in ~/.wiki-dispatcher/config.toml[/]")
            raise typer.Exit(1)

    return wrapper


# ---------------------------------------------------------------- top level
@app.callback()
def _main():
    """wiki-dispatcher"""


@app.command()
def version():
    con.print(f"wiki-dispatcher {__version__}")


@app.command()
def init(vault: Optional[Path] = VaultOpt):
    """Create ~/.wiki-dispatcher/config.toml (and mount a vault if given)."""
    cfg = _cfg(vault)
    p = write_default_config(cfg)
    con.print(f"config: {p}")
    if cfg.vault:
        mount(cfg.vault)


@app.command()
def mount(vault: Path):
    """Set the default vault and build its index."""
    cfg = load_config(vault)
    write_default_config(cfg)
    toml = cfg.home / "config.toml"
    text = toml.read_text().splitlines()
    text = [f'vault = "{cfg.vault}"' if line.startswith("vault =") else line for line in text]
    toml.write_text("\n".join(text) + "\n")
    stats = _index(cfg, rebuild=True).build()
    con.print(f"mounted [bold]{cfg.vault}[/] → {stats['total']} notes indexed at {cfg.index_db}")


@app.command()
def index(vault: Optional[Path] = VaultOpt, rebuild: bool = False):
    """(Re)build the vault index."""
    cfg = _cfg(vault)
    ix = _index(cfg, rebuild=rebuild)
    con.print(ix.build(rebuild=False))


# ---------------------------------------------------------------- vault ops
@vault_app.command("map")
def vault_map(vault: Optional[Path] = VaultOpt):
    """Census: folders, tags, hubs, orphans, broken links."""
    from .vault.graph import VaultGraph

    cfg = _cfg(vault)
    ix = _index(cfg)
    g = VaultGraph(ix)
    con.print(f"[bold]{cfg.vault.name}[/] — {ix.count()} notes")
    t = Table("hub", "score", "in", "out")
    for p, s, m in g.hubs(10):
        t.add_row(p, str(s), str(m["in"]), str(m["out"]))
    con.print(t)
    con.print("tags:", ", ".join(f"{k}({n})" for k, n in ix.tag_census()[:15]))
    con.print("orphans:", len(ix.orphans()), "broken links:", len(ix.broken_links()))


@vault_app.command("search")
def vault_search(query: str, limit: int = 10, vault: Optional[Path] = VaultOpt):
    ix = _index(_cfg(vault))
    for p, snip, score in ix.search(query, limit):
        con.print(f"[cyan]{p}[/]  {snip.replace(chr(10), ' ')}")


@vault_app.command("read")
def vault_read(name: str, vault: Optional[Path] = VaultOpt):
    ix = _index(_cfg(vault))
    n = ix.get(name)
    if not n:
        raise typer.Exit(f"not found: {name}")
    con.print(Markdown(ix.read(n.path)))


@vault_app.command("branch")
def vault_branch(seed: str, depth: int = 2, budget: int = 8000, pack: bool = True, mermaid: bool = False, vault: Optional[Path] = VaultOpt):
    """Extract a budgeted branch around a seed note."""
    from .vault.graph import VaultGraph
    from .vault.pack import pack_branch

    ix = _index(_cfg(vault))
    g = VaultGraph(ix)
    br = g.branch(seed, depth=depth, budget=budget)
    if mermaid:
        con.print(g.to_mermaid(br.paths))
        return
    if pack:
        con.print(Markdown(pack_branch(ix, br).text))
    else:
        t = Table("hop", "score", "kind", "via", "path", "tok")
        for n in br.nodes:
            t.add_row(str(n.hop), f"{n.score:.2f}", n.kind, Path(n.via).stem, n.path, str(n.tokens))
        con.print(t)
        if br.skipped:
            con.print(f"skipped (budget): {len(br.skipped)}")


@vault_app.command("hubs")
def vault_hubs(limit: int = 10, vault: Optional[Path] = VaultOpt):
    from .vault.graph import VaultGraph

    for p, s, m in VaultGraph(_index(_cfg(vault))).hubs(limit):
        con.print(f"{s:6.2f}  {p}  (in={m['in']} out={m['out']})")


@vault_app.command("paths")
def vault_paths(a: str, b: str, k: int = 3, vault: Optional[Path] = VaultOpt):
    from .vault.graph import VaultGraph

    for p in VaultGraph(_index(_cfg(vault))).paths(a, b, k=k):
        con.print(" → ".join(Path(x).stem for x in p))


@vault_app.command("tag")
def vault_tag(tag: str, vault: Optional[Path] = VaultOpt):
    for p in _index(_cfg(vault)).notes_with_tag(tag):
        con.print(p)


@vault_app.command("orphans")
def vault_orphans(vault: Optional[Path] = VaultOpt):
    for p in _index(_cfg(vault)).orphans():
        con.print(p)


@vault_app.command("broken")
def vault_broken(vault: Optional[Path] = VaultOpt):
    for src, raw in _index(_cfg(vault)).broken_links():
        con.print(f"{src}  →  [[{raw}]]")


# ---------------------------------------------------------------- dispatch
@app.command()
@_llm_guard
def ask(message: str, kind: Optional[str] = typer.Option(None, "--as", help="note|brief|report|outline|table|dataset|marp|canvas|mermaid|wikipage"), out: Optional[Path] = typer.Option(None, "--out"), model: Optional[str] = None, no_save: bool = False, vault: Optional[Path] = VaultOpt):
    """One-shot dispatch: message + vault → deliverable in <vault>/_dispatch (or --out)."""
    from .agent import build_dispatcher
    from .deliver import infer_kind, write_deliverable

    cfg = _cfg(vault)
    if out:
        cfg.out_dir = out
    kind = kind or infer_kind(message)
    con.print(f"[dim]kind={kind} model={model or cfg.models.frontier} vault={cfg.vault}[/]")
    d = build_dispatcher(cfg, model=model, kind=kind)
    res = d.run(message, kind=kind)
    con.print(Markdown(res["text"]))
    if not no_save:
        p = write_deliverable(cfg.deliverables, kind, message, res["text"], res["trace_id"])
        con.print(f"\n[green]saved[/] {p}")
    con.print(f"[dim]trace={res['trace_id']} skills={res['skills']} cost≈${res['cost']} tokens={res['totals']}[/]")


@app.command()
@_llm_guard
def chat(model: Optional[str] = None, vault: Optional[Path] = VaultOpt):
    """Interactive REPL on one thread. /save <kind> writes the last answer as a deliverable; /quit exits."""
    from .agent import build_dispatcher
    from .deliver import write_deliverable

    cfg = _cfg(vault)
    d = build_dispatcher(cfg, model=model)
    con.print(f"[bold]wiki-dispatcher[/] · vault={cfg.vault.name} · thread={d.thread} · /save <kind> · /rate <1-5> · /quit")
    last = None
    while True:
        try:
            msg = con.input("[bold cyan]wd>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg in ("/quit", "/exit"):
            break
        if msg.startswith("/save"):
            if not last:
                con.print("nothing to save yet")
                continue
            kind = (msg.split(maxsplit=1) + ["note"])[1]
            p = write_deliverable(cfg.deliverables, kind, last["message"], last["text"], last["trace_id"])
            con.print(f"[green]saved[/] {p}")
            continue
        if msg.startswith("/rate") and last:
            n = int(msg.split()[1])
            d.traces.rate(last["trace_id"], n)
            con.print(f"rated {last['trace_id']} = {n}")
            continue
        res = d.run(msg)
        last = {**res, "message": msg}
        con.print(Markdown(res["text"]))
        con.print(f"[dim]trace={res['trace_id']} skills={res['skills']} cost≈${res['cost']}[/]")


# ---------------------------------------------------------------- skills
@skills_app.command("list")
def skills_list(archived: bool = False, vault: Optional[Path] = VaultOpt):
    reg = _registry(_cfg(vault))
    t = Table("name", "family", "state", "pin", "v", "uses", "patches", "evals", "description", expand=True)
    t.columns[0].no_wrap = True
    t.columns[-1].overflow = "ellipsis"
    t.columns[-1].no_wrap = True
    for s in reg.all(include_archived=archived):
        t.add_row(s.name, s.family, s.state, "📌" if s.pinned else "", s.version, str(s.usage.get("use_count", 0)), str(s.usage.get("patch_count", 0)), str(len(s.evals())), s.description)
    con.print(t)


@skills_app.command("show")
def skills_show(name: str, file: str = "SKILL.md", vault: Optional[Path] = VaultOpt):
    reg = _registry(_cfg(vault))
    s = reg.get(name)
    if not s:
        raise typer.Exit(f"no skill {name}")
    reg.touch(name, "view")
    con.print(Markdown((s.path / file).read_text()))


@skills_app.command("add")
def skills_add(name: str, family: str = typer.Option(...), description: str = typer.Option(...), body: Path = typer.Option(..., help="file with the SKILL.md body"), purpose: Path = typer.Option(..., help="file with PURPOSE.md"), vault: Optional[Path] = VaultOpt):
    reg = _registry(_cfg(vault))
    s = reg.create(name, family, description, body.read_text(), purpose.read_text(), actor="cli")
    con.print(f"created {s.path}; lint: {reg.validate(s) or 'clean'}")


@skills_app.command("update")
def skills_update(name: str, description: Optional[str] = None, body: Optional[Path] = None, purpose: Optional[Path] = None, state: Optional[str] = None, reason: str = "", vault: Optional[Path] = VaultOpt):
    reg = _registry(_cfg(vault))
    s = reg.update(name, description=description, body=body.read_text() if body else None, purpose=purpose.read_text() if purpose else None, state=state, actor="cli", reason=reason)
    con.print(f"updated {s.name} → v{s.version} state={s.state}; lint: {reg.validate(s) or 'clean'}")


@skills_app.command("archive")
def skills_archive(name: str, reason: str = "", vault: Optional[Path] = VaultOpt):
    con.print(f"archived → {_registry(_cfg(vault)).archive(name, reason=reason)}")


@skills_app.command("restore")
def skills_restore(name: str, vault: Optional[Path] = VaultOpt):
    con.print(f"restored → {_registry(_cfg(vault)).restore(name)}")


@skills_app.command("pin")
def skills_pin(name: str, vault: Optional[Path] = VaultOpt):
    _registry(_cfg(vault)).update(name, pinned=True, reason="pin")
    con.print(f"pinned {name}")


@skills_app.command("unpin")
def skills_unpin(name: str, vault: Optional[Path] = VaultOpt):
    _registry(_cfg(vault)).update(name, pinned=False, reason="unpin")
    con.print(f"unpinned {name}")


@skills_app.command("lint")
def skills_lint(vault: Optional[Path] = VaultOpt):
    problems = _registry(_cfg(vault)).lint_all()
    if not problems:
        con.print("[green]all skills clean[/]")
    for name, ps in problems.items():
        con.print(f"[yellow]{name}[/]")
        for p in ps:
            con.print(f"  - {p}")


@skills_app.command("ledger")
def skills_ledger(name: Optional[str] = None, limit: int = 20, vault: Optional[Path] = VaultOpt):
    for e in _registry(_cfg(vault)).ledger.entries(name, limit):
        con.print(f"{e['ts']}  {e['action']:10} {e['skill']:24} {e['file']:14} by {e['actor']}  {e.get('reason', '')}")


# ---------------------------------------------------------------- garden
@garden_app.command("status")
def garden_status(vault: Optional[Path] = VaultOpt):
    cfg = _cfg(vault)
    g = _garden(cfg)
    traces = g.traces.all()
    rated = [t for t in traces if t.get("rating")]
    con.print(f"skills: {len(g.reg.all())}  patterns: {len(list(g.patterns.glob('*.md')))}  traces: {len(traces)} (rated {len(rated)})  pending: {len(g.pending())}")
    con.print(Markdown(g.index_text()))


@garden_app.command("evolve")
@_llm_guard
def garden_evolve(skill: Optional[str] = None, validate: bool = True, since: Optional[str] = None, vault: Optional[Path] = VaultOpt):
    """Run one WikiSkill iteration: maintain wiki → propose → validate on a copy → stage PENDING."""
    from .agent import eval_runner_factory

    cfg = _cfg(vault)
    g = _garden(cfg)
    prop = g.evolve_once(target=skill, runner_factory=eval_runner_factory(cfg) if validate else None, judge_model=cfg.models.cheap, since_trace=since)
    if not prop:
        con.print("nothing proposed this round")
        return
    con.print(f"[bold]{prop.status}[/] {prop.id}: {prop.change_type} [cyan]{prop.skill}[/]  baseline={prop.baseline} candidate={prop.candidate}")
    con.print(f"see garden/pending/{prop.id}/proposal.md — approve with `wd garden approve {prop.id}`")


@garden_app.command("pending")
def garden_pending(vault: Optional[Path] = VaultOpt):
    for p in _garden(_cfg(vault)).pending():
        con.print(f"{p['id']}  {p['status']:16} {p['change_type']:7} {p['skill']:24} base={p['baseline']} cand={p['candidate']}  {p['rationale'][:80]}")


@garden_app.command("approve")
def garden_approve(pid: str, vault: Optional[Path] = VaultOpt):
    con.print(_garden(_cfg(vault)).approve(pid))


@garden_app.command("reject")
def garden_reject(pid: str, reason: str = typer.Option("", "--reason"), vault: Optional[Path] = VaultOpt):
    con.print(_garden(_cfg(vault)).reject(pid, reason))


@garden_app.command("eval")
@_llm_guard
def garden_eval(skill: str, model: Optional[str] = None, vault: Optional[Path] = VaultOpt):
    """Run a skill's evals against the current library."""
    from .agent import eval_runner_factory
    from .garden.evals import load_cases, run_evals

    cfg = _cfg(vault)
    reg = _registry(cfg)
    s = reg.get(skill)
    if not s:
        raise typer.Exit(f"no skill {skill}")
    report = run_evals(skill, load_cases(s.path), eval_runner_factory(cfg, model)(reg.root), judge_model=cfg.models.cheap)
    con.print(json.dumps(report.to_dict(), indent=1))


@garden_app.command("sweep")
def garden_sweep(stale_days: int = 14, archive_days: int = 30, vault: Optional[Path] = VaultOpt):
    """Deterministic curator: active→stale→archived by inactivity (never deletes; skips pinned)."""
    for name, state in _registry(_cfg(vault)).sweep(stale_days, archive_days):
        con.print(f"{name} → {state}")


@garden_app.command("rate")
def garden_rate(trace_id: str, rating: int, note: str = "", vault: Optional[Path] = VaultOpt):
    """Rate a trace 1-5. Ratings drive which traces the maintainer samples as failing/passing."""
    from .trace import TraceWriter

    rec = TraceWriter(_cfg(vault).traces_dir).rate(trace_id, rating, note)
    con.print(f"{rec['id']} → {rec['outcome']}")


# ---------------------------------------------------------------- usage / fixture
@app.command()
def usage(days: Optional[float] = None, vault: Optional[Path] = VaultOpt):
    """Token and cost summary from ~/.wiki-dispatcher/usage.jsonl."""
    from .usage import summarize

    con.print(json.dumps(summarize(_cfg(vault).usage_log, days), indent=1))


@app.command()
def fixture(dest: Path):
    """Generate the synthetic llm-wiki fixture vault."""
    from .fixture import make_fixture_vault

    con.print(f"fixture vault at {make_fixture_vault(dest)}  →  `wd mount {dest}`")


if __name__ == "__main__":
    app()
