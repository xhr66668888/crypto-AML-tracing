# Swapping from InMemoryStore to PostgreSQL

> ⚠️ **Round-one acceptance status: blocked.** The `PostgresStore`
> implementation in `services/api/app/storage/postgres.py` raises
> `NotImplementedError` on `get_screening_event` and has `TODO`s on
> `list_screening_events`. It is **not** safe to point production traffic at
> it. See
> [`docs/acceptance-review.md § db-storage-engineer`](../acceptance-review.md#db-storage-engineer)
> for the remediation choice (delete vs. integration-test). Until that is
> resolved, this document describes the *intended* swap path, not a working
> one.

This document explains how to migrate the AML Tracing system from the default in-memory storage to PostgreSQL.

## Overview

The storage layer uses a **StorageAdapter** interface that allows swapping between implementations:

| Store | When to use | Data persistence |
|-------|-------------|------------------|
| `InMemoryStore` | Default, demo mode, development | Lost on restart |
| `PostgresStore` | Production, multi-session, data persistence | Persistent |

## Quick Start

### 1. Install PostgreSQL dependencies

```bash
pip install psycopg2-binary
```

### 2. Set DATABASE_URL

Add to your `.env` file:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/aml_tracing
```

Format: `postgresql://<user>:<password>@<host>:<port>/<database>`

### 3. Create the database

```bash
createdb aml_tracing
```

### 4. Apply the schema

```bash
psql -d aml_tracing -f docs/database/schema.sql
```

### 5. Restart the API

```bash
cd services/api
uvicorn app.main:app --reload
```

The storage factory automatically detects `DATABASE_URL` and uses `PostgresStore`.

## How It Works

### Storage Factory

The `get_store()` function in `app/storage/factory.py` handles the selection:

```python
from app.storage import get_store

# Returns InMemoryStore if DATABASE_URL is not set
# Returns PostgresStore if DATABASE_URL is set
store = get_store()
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | *(empty)* | PostgreSQL connection string. If empty, uses InMemoryStore. |

### Fallback Behavior

If `DATABASE_URL` is set but `psycopg2` is not installed:
- A warning is emitted
- System falls back to `InMemoryStore`
- No data loss or crash

## Schema Details

The schema (`docs/database/schema.sql`) creates:

- **Core tables**: `investigations`, `addresses`, `transactions`, `investigation_edges`
- **Risk tables**: `risk_labels`, `risk_scores`, `screening_events`, `risk_source_hits`
- **Analysis tables**: `pattern_signals`, `network_metrics`, `ml_features`, `ml_predictions`
- **AI/ML tables**: `experiment_runs`, `ai_reports`
- **Operations tables**: `watchlist_entries`, `source_sync_runs`, `api_cache`, `audit_logs`

All tables include:
- UUID primary keys
- `created_at` timestamps with timezone
- JSONB columns for flexible metadata
- Appropriate indexes for common query patterns

## Docker Compose Setup

For local development with Docker:

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aml_tracing
      POSTGRES_USER: aml
      POSTGRES_PASSWORD: aml_dev_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docs/database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql

volumes:
  pgdata:
```

Then set:
```bash
DATABASE_URL=postgresql://aml:aml_dev_password@localhost:5432/aml_tracing
```

## Verification

### 1. Check store type

The `/health` endpoint shows demo mode status. Check logs for:
```
Using PostgresStore with DATABASE_URL=postgresql://...
```

### 2. Run tests

```bash
PYTHONPATH=services/api pytest -q services/api/app/tests
```

Tests run against InMemoryStore by default (no DATABASE_URL in test environment).

### 3. Verify persistence

1. Create an investigation via API
2. Restart the server
3. Query the investigation — it should still exist

## Migration from InMemoryStore

**No data migration is possible** — InMemoryStore data is ephemeral.

When swapping to PostgreSQL:
1. All new data goes to PostgreSQL
2. Previous in-memory data is lost
3. This is expected for demo/development → production transition

## Troubleshooting

### psycopg2 installation fails

```bash
# On Ubuntu/Debian
sudo apt-get install libpq-dev
pip install psycopg2-binary

# On macOS
brew install postgresql
pip install psycopg2-binary
```

### Connection refused

1. Check PostgreSQL is running: `pg_isready`
2. Verify DATABASE_URL credentials
3. Check firewall/network settings

### Schema already exists

The schema uses `CREATE TABLE IF NOT EXISTS`, so re-running is safe:
```bash
psql -d aml_tracing -f docs/database/schema.sql
```

## Future Enhancements

- [ ] Connection pooling (asyncpg or psycopg2 pool)
- [ ] Migration tooling (Alembic)
- [ ] Read replicas support
- [ ] Connection health checks
- [ ] Graceful degradation on connection loss
