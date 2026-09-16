"""Vault layer: parse → index → graph → pack. Deterministic; no LLM calls."""

from .index import VaultIndex
from .parse import parse_note

__all__ = ["VaultIndex", "parse_note"]
