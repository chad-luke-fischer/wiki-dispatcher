"""Deliverables: infer the type from the ask, wrap the agent's output in an Obsidian-native shell."""

from .router import infer_kind
from .writers import write_deliverable

__all__ = ["infer_kind", "write_deliverable"]
