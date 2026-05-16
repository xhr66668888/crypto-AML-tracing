"""Storage adapters.

This module provides the storage boundary for the AML tracing system.

Usage:
    from app.storage import get_store, StorageAdapter, InMemoryStore

    # Get the configured store (InMemoryStore by default, PostgresStore if DATABASE_URL is set)
    store = get_store()

    # Type hint for dependency injection
    def my_function(store: StorageAdapter) -> None: ...
"""
from app.storage.base import StorageAdapter
from app.storage.factory import get_store
from app.storage.memory import InMemoryStore

__all__ = ["StorageAdapter", "InMemoryStore", "get_store"]
