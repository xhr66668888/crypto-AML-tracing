"""Storage factory — selects InMemoryStore or PostgresStore based on DATABASE_URL.

Usage:
    from app.storage.factory import get_store
    store = get_store()  # Returns InMemoryStore by default, PostgresStore if DATABASE_URL is set
"""
from __future__ import annotations

import importlib
import os
import warnings

from app.storage.base import StorageAdapter
from app.storage.memory import InMemoryStore


def _psycopg2_available() -> bool:
    """Check if psycopg2 is importable."""
    return importlib.util.find_spec("psycopg2") is not None


def get_store() -> StorageAdapter:
    """Return the appropriate storage adapter based on environment configuration.

    - If DATABASE_URL is set and psycopg2 is available → PostgresStore
    - Otherwise → InMemoryStore (default, no external dependencies)
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if database_url:
        if not _psycopg2_available():
            warnings.warn(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Falling back to InMemoryStore. Install psycopg2-binary to use PostgreSQL.",
                stacklevel=2,
            )
            return InMemoryStore()

        from app.storage.postgres import PostgresStore
        return PostgresStore(dsn=database_url)
    else:
        return InMemoryStore()
