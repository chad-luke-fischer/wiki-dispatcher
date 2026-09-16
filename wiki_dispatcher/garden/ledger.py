"""Append-only mutation ledger with content-addressed before/after blobs (Hermes-style).

Every change to a skill — by the CLI, by the agent, or by the evolve loop — is recorded here
so it can be inspected and rolled back. Never delete; archive.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class Ledger:
    def __init__(self, garden_root: Path):
        self.root = Path(garden_root)
        self.path = self.root / "ledger.jsonl"
        self.blobs = self.root / ".blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)

    def blob(self, content: str | None) -> str | None:
        if content is None:
            return None
        h = hashlib.sha256(content.encode()).hexdigest()
        p = self.blobs / h
        if not p.exists():
            p.write_text(content, encoding="utf-8")
        return h

    def read_blob(self, h: str) -> str:
        return (self.blobs / h).read_text(encoding="utf-8")

    def record(self, action: str, skill: str, file: str, before: str | None, after: str | None, actor: str, reason: str = "", extra: dict | None = None) -> dict:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": action,  # create | patch | archive | restore | write_file | remove_file | evolve-apply
            "skill": skill,
            "file": file,
            "before": self.blob(before),
            "after": self.blob(after),
            "actor": actor,  # cli | agent | evolve | user
            "reason": reason,
            **(extra or {}),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def entries(self, skill: str | None = None, limit: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        if skill:
            rows = [r for r in rows if r["skill"] == skill]
        return rows[-limit:]
