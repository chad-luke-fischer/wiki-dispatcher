"""Configuration and path resolution.

Layout (all overridable):

    ~/.wiki-dispatcher/            DISPATCHER_HOME  (env WD_HOME)
      config.toml                  user config
      usage.jsonl                  per-run token/cost ledger
      vaults/<slug>/index.db       per-vault SQLite index cache (keeps the vault clean)
      sessions/<thread>.jsonl      conversation checkpoints (langgraph sqlite)
    <repo>/skills/<family>/<skill>/SKILL.md   the skill library (git-tracked)
    <repo>/garden/                 the pattern wiki + evolution ledger (git-tracked, Obsidian-openable)

The vault itself is never written to except through `file-back`, which is human-gated.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOME = Path(os.environ.get("WD_HOME", Path.home() / ".wiki-dispatcher"))

SKILL_FAMILIES = ("traverse", "garden", "deliver", "wiki")


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "vault"


@dataclass
class ModelTiers:
    """Model-agnostic routing. Strings are `init_chat_model` identifiers ("provider:model")."""

    frontier: str = "anthropic:claude-sonnet-4-6"  # dispatch + synthesis
    worker: str = "anthropic:claude-haiku-4-5"  # traversal subagents
    cheap: str = "anthropic:claude-haiku-4-5"  # classification, wiki maintenance, judges
    # Example local option (does not melt the machine if you pick a small model):
    # cheap: str = "ollama:qwen3:4b"


@dataclass
class Config:
    home: Path = DEFAULT_HOME
    vault: Path | None = None
    out_dir: Path | None = None  # deliverables; default <vault>/_dispatch
    skills_root: Path = REPO_ROOT / "skills"
    garden_root: Path = REPO_ROOT / "garden"
    models: ModelTiers = field(default_factory=ModelTiers)
    context_budget_tokens: int = 12_000
    default_depth: int = 2
    write_vault: bool = False  # hard gate; file-back still interrupts for approval
    price_table: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            # USD per 1M tokens (input, output). Edit freely; only used for estimates.
            "anthropic:claude-sonnet-4-6": (3.0, 15.0),
            "anthropic:claude-haiku-4-5": (1.0, 5.0),
            "anthropic:claude-opus-4-6": (15.0, 75.0),
        }
    )

    # ---- derived paths -------------------------------------------------
    @property
    def vault_slug(self) -> str:
        return slugify(self.vault.name) if self.vault else "no-vault"

    @property
    def vault_cache(self) -> Path:
        return self.home / "vaults" / self.vault_slug

    @property
    def index_db(self) -> Path:
        return self.vault_cache / "index.db"

    @property
    def usage_log(self) -> Path:
        return self.home / "usage.jsonl"

    @property
    def sessions_dir(self) -> Path:
        return self.home / "sessions"

    @property
    def traces_dir(self) -> Path:
        return self.garden_root / "raw" / "traces"

    @property
    def pending_dir(self) -> Path:
        return self.garden_root / "pending"

    @property
    def deliverables(self) -> Path:
        if self.out_dir:
            return self.out_dir
        if self.vault:
            return self.vault / "_dispatch"
        return self.home / "out"

    def ensure_dirs(self) -> None:
        for p in (self.home, self.vault_cache, self.sessions_dir, self.traces_dir, self.pending_dir):
            p.mkdir(parents=True, exist_ok=True)


def load_config(vault: str | Path | None = None, home: Path | None = None) -> Config:
    """Load ~/.wiki-dispatcher/config.toml, then apply CLI overrides."""
    cfg = Config(home=home or DEFAULT_HOME)
    toml_path = cfg.home / "config.toml"
    if toml_path.exists():
        data = tomllib.loads(toml_path.read_text())
        if v := data.get("vault"):
            cfg.vault = Path(v).expanduser()
        if o := data.get("out_dir"):
            cfg.out_dir = Path(o).expanduser()
        if m := data.get("models"):
            cfg.models = ModelTiers(**{**cfg.models.__dict__, **m})
        cfg.context_budget_tokens = int(data.get("context_budget_tokens", cfg.context_budget_tokens))
        cfg.default_depth = int(data.get("default_depth", cfg.default_depth))
        cfg.write_vault = bool(data.get("write_vault", cfg.write_vault))
        if pt := data.get("prices"):
            cfg.price_table.update({k: tuple(v) for k, v in pt.items()})
    if vault:
        cfg.vault = Path(vault).expanduser().resolve()
    if env_vault := os.environ.get("WD_VAULT"):
        cfg.vault = cfg.vault or Path(env_vault).expanduser().resolve()
    return cfg


def write_default_config(cfg: Config) -> Path:
    cfg.home.mkdir(parents=True, exist_ok=True)
    p = cfg.home / "config.toml"
    if not p.exists():
        p.write_text(
            f'''# wiki-dispatcher config
vault = "{cfg.vault or ""}"
# out_dir = "~/Documents/dispatch-out"
context_budget_tokens = {cfg.context_budget_tokens}
default_depth = {cfg.default_depth}
write_vault = false

[models]
frontier = "{cfg.models.frontier}"
worker = "{cfg.models.worker}"
cheap = "{cfg.models.cheap}"

# [prices]                      # USD per 1M tokens: [input, output]
# "ollama:qwen3:4b" = [0.0, 0.0]
'''
        )
    return p
