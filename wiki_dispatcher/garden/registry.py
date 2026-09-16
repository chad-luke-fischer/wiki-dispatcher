"""Skill registry: discovery, validation, telemetry, lifecycle, and CRUD with ledgering.

Skill layout (agentskills.io compatible, + WikiSkill's PURPOSE.md, + evals):

    skills/<family>/<name>/
      SKILL.md          frontmatter: name, description, [metadata.wd: family, state, pinned, version]
      PURPOSE.md        why this skill exists; which garden patterns motivated it
      evals/evals.json  [{id, prompt, expected, assertions:[...]}]
      references/ scripts/ assets/   optional

Lifecycle (Hermes-inspired): seed → active → stale → archived. `pinned` skills are never
auto-archived. Archive = move to garden/.archive/<name>/ (recoverable), never delete.
Telemetry lives in garden/.usage.json: use_count, view_count, last_used_at, patch_count,
created_by, reuse_after_patch.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from ..config import SKILL_FAMILIES
from .ledger import Ledger

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
STATES = ("seed", "active", "stale", "archived")


@dataclass
class Skill:
    name: str
    family: str
    description: str
    path: Path
    state: str = "active"
    pinned: bool = False
    version: str = "0.1.0"
    metadata: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def purpose_md(self) -> Path:
        return self.path / "PURPOSE.md"

    @property
    def evals_json(self) -> Path:
        return self.path / "evals" / "evals.json"

    def body(self) -> str:
        return frontmatter.load(self.skill_md).content

    def purpose(self) -> str:
        return self.purpose_md.read_text() if self.purpose_md.exists() else ""

    def evals(self) -> list[dict]:
        return json.loads(self.evals_json.read_text()) if self.evals_json.exists() else []

    def summary(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "state": self.state,
            "pinned": self.pinned,
            "version": self.version,
            "description": self.description,
            "use_count": self.usage.get("use_count", 0),
            "last_used_at": self.usage.get("last_used_at"),
            "patch_count": self.usage.get("patch_count", 0),
            "evals": len(self.evals()),
        }


class SkillRegistry:
    def __init__(self, skills_root: Path, garden_root: Path):
        self.root = Path(skills_root)
        self.garden = Path(garden_root)
        self.usage_path = self.garden / ".usage.json"
        self.archive_dir = self.garden / ".archive"
        self.ledger = Ledger(self.garden)

    # ---- telemetry -----------------------------------------------------
    def _usage(self) -> dict:
        return json.loads(self.usage_path.read_text()) if self.usage_path.exists() else {}

    def _save_usage(self, u: dict) -> None:
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(json.dumps(u, indent=1, sort_keys=True))

    def touch(self, name: str, event: str) -> None:
        """event: use | view | patch"""
        u = self._usage()
        rec = u.setdefault(name, {"use_count": 0, "view_count": 0, "patch_count": 0, "created_by": "human"})
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        if event == "use":
            rec["use_count"] += 1
            rec["last_used_at"] = now
            if rec.get("patch_generation", 0) > rec.get("last_reused_patch_generation", 0):
                rec["last_reused_patch_generation"] = rec["patch_generation"]
                rec["reuse_after_patch"] = True
        elif event == "view":
            rec["view_count"] += 1
            rec["last_viewed_at"] = now
        elif event == "patch":
            rec["patch_count"] += 1
            rec["patch_generation"] = rec.get("patch_generation", 0) + 1
            rec["last_patched_at"] = now
            rec["reuse_after_patch"] = False
        self._save_usage(u)

    # ---- discovery -----------------------------------------------------
    def families(self) -> list[str]:
        found = [p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        return [f for f in SKILL_FAMILIES if f in found] + [f for f in found if f not in SKILL_FAMILIES]

    def family_dirs(self) -> list[str]:
        """Paths relative to the backend root, in the form deepagents' `skills=` expects."""
        return [f"/skills/{f}/" for f in self.families()]

    def load(self, path: Path) -> Skill | None:
        md = path / "SKILL.md"
        if not md.exists():
            return None
        post = frontmatter.load(md)
        meta = dict(post.metadata)
        wd = (meta.get("metadata") or {}).get("wd", {}) if isinstance(meta.get("metadata"), dict) else {}
        name = str(meta.get("name", path.name))
        return Skill(
            name=name,
            family=path.parent.name,
            description=str(meta.get("description", "")),
            path=path,
            state=str(wd.get("state", "active")),
            pinned=bool(wd.get("pinned", False)),
            version=str(wd.get("version", meta.get("version", "0.1.0"))),
            metadata=meta,
            usage=self._usage().get(name, {}),
        )

    def all(self, include_archived: bool = False) -> list[Skill]:
        out = []
        for fam in self.families():
            for d in sorted((self.root / fam).iterdir()):
                if d.is_dir() and (s := self.load(d)):
                    out.append(s)
        if include_archived and self.archive_dir.exists():
            for d in sorted(self.archive_dir.iterdir()):
                if d.is_dir() and (s := self.load(d)):
                    s.state = "archived"
                    out.append(s)
        return out

    def get(self, name: str) -> Skill | None:
        for s in self.all(include_archived=True):
            if s.name == name:
                return s
        return None

    def validate(self, skill: Skill) -> list[str]:
        problems = []
        if not NAME_RE.match(skill.name):
            problems.append(f"name '{skill.name}' must be lowercase [a-z0-9-], 1-64 chars, no leading/trailing hyphen")
        if skill.name != skill.path.name:
            problems.append(f"name '{skill.name}' must match directory '{skill.path.name}'")
        if not skill.description:
            problems.append("description is required")
        if len(skill.description) > 1024:
            problems.append("description > 1024 chars")
        body = skill.body()
        if len(body.splitlines()) > 500:
            problems.append("SKILL.md body > 500 lines; move detail to references/")
        if not skill.purpose_md.exists():
            problems.append("PURPOSE.md missing (why does this skill exist? which patterns motivated it?)")
        # negative tool claims, ignoring quoted/parenthesised examples (skills may *describe* the rule)
        unquoted = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'|`[^`\n]*`|\([^)\n]*\)', "", body)
        if re.search(r"\b(does not work|doesn't work|never works|do not work|is broken)\b", unquoted, re.I):
            problems.append("contains a negative tool claim — these harden into refusals; state the working path instead")
        if len(re.findall(r"#\d{3,}|PR-?\d+", body)) >= 4:
            problems.append("incident-log shape: many PR/issue references; write rules, not history")
        return problems

    def lint_all(self) -> dict[str, list[str]]:
        return {s.name: p for s in self.all() if (p := self.validate(s))}

    # ---- CRUD (all ledgered) -------------------------------------------
    def create(self, name: str, family: str, description: str, body: str, purpose: str, actor: str = "cli", evals: list[dict] | None = None, created_by: str | None = None) -> Skill:
        if not NAME_RE.match(name):
            raise ValueError(f"invalid skill name: {name}")
        if self.get(name):
            raise FileExistsError(f"skill exists: {name}")
        d = self.root / family / name
        d.mkdir(parents=True)
        content = _skill_md(name, description, body, family=family, state="seed")
        (d / "SKILL.md").write_text(content)
        (d / "PURPOSE.md").write_text(purpose.strip() + "\n")
        if evals:
            (d / "evals").mkdir()
            (d / "evals" / "evals.json").write_text(json.dumps(evals, indent=1))
        self.ledger.record("create", name, "SKILL.md", None, content, actor, "create")
        u = self._usage()
        u[name] = {"use_count": 0, "view_count": 0, "patch_count": 0, "created_by": created_by or actor, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self._save_usage(u)
        return self.load(d)

    def update(self, name: str, *, description: str | None = None, body: str | None = None, purpose: str | None = None, state: str | None = None, pinned: bool | None = None, actor: str = "cli", reason: str = "") -> Skill:
        s = self.get(name)
        if not s:
            raise FileNotFoundError(name)
        before = s.skill_md.read_text()
        post = frontmatter.loads(before)
        if description is not None:
            post.metadata["description"] = description
        wd = post.metadata.setdefault("metadata", {}).setdefault("wd", {})
        wd.setdefault("family", s.family)
        if state is not None:
            if state not in STATES:
                raise ValueError(f"state must be one of {STATES}")
            wd["state"] = state
        if pinned is not None:
            wd["pinned"] = pinned
        if body is not None:
            post.content = body.strip() + "\n"
            wd["version"] = _bump(str(wd.get("version", s.version)))
        after = frontmatter.dumps(post) + "\n"
        s.skill_md.write_text(after)
        self.ledger.record("patch", name, "SKILL.md", before, after, actor, reason)
        if purpose is not None:
            pb = s.purpose() or None
            s.purpose_md.write_text(purpose.strip() + "\n")
            self.ledger.record("patch", name, "PURPOSE.md", pb, purpose, actor, reason)
        if body is not None or description is not None:
            self.touch(name, "patch")
        return self.get(name)

    def write_file(self, name: str, rel: str, content: str, actor: str = "cli", reason: str = "") -> Path:
        s = self.get(name)
        if not s:
            raise FileNotFoundError(name)
        if rel.split("/")[0] not in ("references", "scripts", "assets", "evals"):
            raise ValueError("support files must live under references/, scripts/, assets/ or evals/")
        p = s.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        before = p.read_text() if p.exists() else None
        p.write_text(content)
        self.ledger.record("write_file", name, rel, before, content, actor, reason)
        return p

    def archive(self, name: str, actor: str = "cli", reason: str = "") -> Path:
        s = self.get(name)
        if not s:
            raise FileNotFoundError(name)
        if s.pinned:
            raise PermissionError(f"{name} is pinned; unpin first")
        if s.state == "archived":
            return s.path
        self.update(name, state="archived", actor=actor, reason=reason or "archive")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        dest = self.archive_dir / name
        (dest.parent / f"{name}.family").write_text(s.family)
        shutil.move(str(s.path), str(dest))
        self.ledger.record("archive", name, "", None, None, actor, reason, {"from": str(s.path)})
        return dest

    def restore(self, name: str, actor: str = "cli") -> Path:
        src = self.archive_dir / name
        if not src.exists():
            raise FileNotFoundError(f"not archived: {name}")
        fam_file = self.archive_dir / f"{name}.family"
        family = fam_file.read_text().strip() if fam_file.exists() else "traverse"
        dest = self.root / family / name
        shutil.move(str(src), str(dest))
        fam_file.unlink(missing_ok=True)
        self.update(name, state="active", actor=actor, reason="restore")
        self.ledger.record("restore", name, "", None, None, actor, "restore")
        return dest

    # ---- lifecycle sweep (deterministic curator phase 1) ---------------
    def sweep(self, stale_after_days: int = 14, archive_after_days: int = 30, actor: str = "curator") -> list[tuple[str, str]]:
        """active→stale→archived by last activity. Skills with use_count==0 are never archived
        (absence of evidence, not staleness). Pinned skills are skipped. Returns transitions."""
        now = time.time()
        moves = []
        for s in self.all():
            if s.pinned or s.state == "seed":
                continue
            last = s.usage.get("last_used_at") or s.usage.get("last_patched_at") or s.usage.get("created_at")
            if not last:
                continue
            age_days = (now - time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))) / 86400
            if s.state == "active" and age_days > stale_after_days:
                self.update(s.name, state="stale", actor=actor, reason=f"no activity for {int(age_days)}d")
                moves.append((s.name, "stale"))
            elif s.state == "stale" and age_days > archive_after_days and s.usage.get("use_count", 0) > 0:
                self.archive(s.name, actor=actor, reason=f"stale for {int(age_days)}d")
                moves.append((s.name, "archived"))
        return moves


def _bump(v: str) -> str:
    parts = v.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        return v
    return ".".join(parts)


def _skill_md(name: str, description: str, body: str, family: str, state: str = "active", version: str = "0.1.0") -> str:
    post = frontmatter.Post(body.strip() + "\n")
    post.metadata = {
        "name": name,
        "description": description,
        "metadata": {"wd": {"family": family, "state": state, "pinned": False, "version": version}},
    }
    return frontmatter.dumps(post) + "\n"
