# PostgreSQL Persistence — Future Design Note

**Status:** Forward-looking. V1 ships with `InMemoryStore` only.

## Decision (2026-05-16, round-one acceptance)

`PostgresStore` (`services/api/app/storage/postgres.py`, 442 lines) was
deleted during round-one Karpathy §2 cleanup. It raised `NotImplementedError`
on `get_screening_event` and had `TODO`s on `list_screening_events`. No
caller existed in `services/` or `main.py`.

**Option A approved** by `aml-architect`: delete the speculative adapter.
The SQL schema in `docs/database/schema.sql` remains as the persistence
contract. When V1 actually needs persistence, write the adapter then,
with an integration test gated on `DATABASE_URL`.

## Architecture (for future implementation)

**Round-two note (2026-05-16):** The `DATABASE_URL` branch in
`app/storage/factory.py` was removed in round two because the `PostgresStore`
adapter it called no longer exists. A future PR that re-implements the adapter
must also restore the factory branch (see Step 0 in the checklist below).

The storage layer uses a `StorageAdapter` abstract base class. Implementations:

| Store | Status | Data persistence |
|-------|--------|------------------|
| `InMemoryStore` | V1 default | Lost on restart |
| `PostgresStore` | Not yet implemented | Will be persistent |

### Schema

`docs/database/schema.sql` defines the full relational schema:

- **Core tables:** `investigations`, `addresses`, `transactions`, `investigation_edges`
- **Risk tables:** `risk_labels`, `risk_scores`, `screening_events`, `risk_source_hits`
- **Analysis tables:** `pattern_signals`, `network_metrics`, `ml_features`, `ml_predictions`
- **AI/ML tables:** `experiment_runs`, `ai_reports`
- **Operations tables:** `watchlist_entries`, `source_sync_runs`, `api_cache`, `audit_logs`

All tables include UUID primary keys, `created_at` timestamps with timezone,
JSONB columns for flexible metadata, and appropriate indexes.

### Environment

When implemented, the adapter should be gated behind `DATABASE_URL`:

```
DATABASE_URL=postgresql://user:password@host:port/database
```

If `DATABASE_URL` is unset, the system falls back to `InMemoryStore`.

### Docker Compose

```yaml
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

## Implementation checklist (for future PR)

- [ ] **Step 0** — restore the `DATABASE_URL` branch in `app/storage/factory.py` that round two removed.
- [ ] Implement `PostgresStore(StorageAdapter)` using `psycopg2` or `asyncpg`
- [ ] Gate behind `DATABASE_URL` in `app/storage/factory.py`
- [ ] Add integration test (skipped by default, enabled when `DATABASE_URL` is set)
- [ ] Round-trip: investigation, screening event, watchlist entry
- [ ] Remove all `NotImplementedError` and `TODO` markers
- [ ] Update this doc with working swap instructions
