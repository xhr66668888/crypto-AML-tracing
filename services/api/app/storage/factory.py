"""Storage factory — returns local MVP storage."""
from __future__ import annotations

from app.core.config import get_settings
from app.storage.base import StorageAdapter
from app.storage.memory import InMemoryStore


def get_store() -> StorageAdapter:
    """Return the local storage adapter."""
    settings = get_settings()
    return InMemoryStore(watchlist_path=settings.watchlist_data_path)
