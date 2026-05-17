"""Storage factory — returns InMemoryStore unconditionally."""
from __future__ import annotations

from app.storage.base import StorageAdapter
from app.storage.memory import InMemoryStore


def get_store() -> StorageAdapter:
    """Return the in-memory storage adapter."""
    return InMemoryStore()
