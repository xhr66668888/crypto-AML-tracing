CREATE TABLE IF NOT EXISTS investigations (
  id UUID PRIMARY KEY,
  target TEXT NOT NULL,
  target_type TEXT NOT NULL,
  chain_id TEXT NOT NULL DEFAULT '1',
  depth INTEGER NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS addresses (
  address TEXT PRIMARY KEY,
  first_seen_at TIMESTAMPTZ DEFAULT now(),
  last_seen_at TIMESTAMPTZ DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS transactions (
  tx_hash TEXT PRIMARY KEY,
  chain_id TEXT NOT NULL DEFAULT '1',
  block_number BIGINT,
  timestamp TIMESTAMPTZ,
  from_address TEXT,
  to_address TEXT,
  value_eth NUMERIC,
  raw_payload JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS investigation_edges (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  tx_hash TEXT NOT NULL,
  source_address TEXT NOT NULL,
  target_address TEXT NOT NULL,
  hop INTEGER NOT NULL,
  value_eth NUMERIC,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS risk_labels (
  id UUID PRIMARY KEY,
  address TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  evidence TEXT NOT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_scores (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  rule_score NUMERIC NOT NULL,
  raindrop_score NUMERIC NOT NULL,
  final_risk_score NUMERIC NOT NULL,
  final_risk_level TEXT NOT NULL,
  disposition_hint TEXT NOT NULL DEFAULT 'allow',
  feature_summary JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS screening_events (
  id UUID PRIMARY KEY,
  chain_id TEXT NOT NULL DEFAULT '1',
  asset TEXT NOT NULL,
  direction TEXT NOT NULL,
  from_address TEXT NOT NULL,
  to_address TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  customer_id TEXT,
  team_id TEXT,
  tx_hash TEXT,
  risk_score NUMERIC NOT NULL,
  risk_level TEXT NOT NULL,
  disposition TEXT NOT NULL,
  evidence_summary JSONB NOT NULL DEFAULT '[]',
  recommended_actions JSONB NOT NULL DEFAULT '[]',
  data_freshness JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_source_hits (
  id UUID PRIMARY KEY,
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  screening_event_id UUID REFERENCES screening_events(id) ON DELETE CASCADE,
  address TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  label TEXT NOT NULL,
  evidence TEXT NOT NULL,
  confidence NUMERIC NOT NULL DEFAULT 1,
  direct_hit BOOLEAN NOT NULL DEFAULT false,
  source_updated_at TIMESTAMPTZ,
  raw_payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pattern_signals (
  id UUID PRIMARY KEY,
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  screening_event_id UUID REFERENCES screening_events(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  severity TEXT NOT NULL,
  score NUMERIC NOT NULL,
  subject TEXT NOT NULL,
  evidence TEXT NOT NULL,
  confidence NUMERIC NOT NULL DEFAULT 0.75,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS network_metrics (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  value NUMERIC NOT NULL,
  subject TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ml_features (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  feature_schema_version TEXT NOT NULL,
  tensor_uri TEXT,
  summary JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ml_predictions (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  model_version TEXT NOT NULL,
  score NUMERIC NOT NULL,
  explanation JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_runs (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  model_version TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  metrics JSONB NOT NULL DEFAULT '{}',
  params JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_reports (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  report_markdown TEXT NOT NULL,
  used_external_llm BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watchlist_entries (
  address TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_sync_runs (
  id UUID PRIMARY KEY,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_changed INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS api_cache (
  cache_key TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  payload JSONB NOT NULL,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  actor TEXT NOT NULL DEFAULT 'local-user',
  action TEXT NOT NULL,
  subject TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_investigation_edges_investigation_hop ON investigation_edges (investigation_id, hop);
CREATE INDEX IF NOT EXISTS idx_transactions_from_address ON transactions (from_address);
CREATE INDEX IF NOT EXISTS idx_transactions_to_address ON transactions (to_address);
CREATE INDEX IF NOT EXISTS idx_risk_labels_address ON risk_labels (address);
CREATE INDEX IF NOT EXISTS idx_screening_events_created_at ON screening_events (created_at);
CREATE INDEX IF NOT EXISTS idx_screening_events_addresses ON screening_events (from_address, to_address);
CREATE INDEX IF NOT EXISTS idx_risk_source_hits_address ON risk_source_hits (address);
CREATE INDEX IF NOT EXISTS idx_pattern_signals_investigation ON pattern_signals (investigation_id);
CREATE INDEX IF NOT EXISTS idx_pattern_signals_screening ON pattern_signals (screening_event_id);
CREATE INDEX IF NOT EXISTS idx_api_cache_provider ON api_cache (provider);
