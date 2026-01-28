-- OpenSec-Env SQLite schema (Phase 0)

CREATE TABLE IF NOT EXISTS email_logs (
  email_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  sender TEXT NOT NULL,
  recipient TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  is_phish INTEGER NOT NULL DEFAULT 0 CHECK (is_phish IN (0, 1)),
  injection_id TEXT,
  trust_tier TEXT,
  source TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_logs (
  auth_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  user_id TEXT NOT NULL,
  host_id TEXT NOT NULL,
  source_ip TEXT,
  auth_type TEXT NOT NULL,
  success INTEGER NOT NULL CHECK (success IN (0, 1)),
  trust_tier TEXT,
  source TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS netflow (
  flow_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  src_host TEXT NOT NULL,
  dst_host TEXT,
  dst_domain TEXT,
  dst_port INTEGER,
  protocol TEXT,
  bytes_sent INTEGER,
  bytes_received INTEGER,
  trust_tier TEXT,
  source TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS process_events (
  event_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  host_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  process_name TEXT NOT NULL,
  command_line TEXT,
  parent_process TEXT,
  trust_tier TEXT,
  source TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
  alert_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  related_log_id TEXT,
  injection_id TEXT,
  trust_tier TEXT,
  source TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_injections (
  injection_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  surface TEXT NOT NULL,
  payload TEXT NOT NULL,
  expected_violation TEXT NOT NULL,
  target_action TEXT,
  target_params TEXT,
  evidence_ids TEXT,
  injection_type TEXT,
  objective TEXT,
  source TEXT
);

CREATE TABLE IF NOT EXISTS attacker_decisions (
  decision_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  attacker_state TEXT NOT NULL,
  agent_action_hash TEXT NOT NULL,
  attacker_context_hash TEXT NOT NULL,
  decision_json TEXT NOT NULL,
  model TEXT NOT NULL,
  temperature REAL NOT NULL,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_attacker_cache
  ON attacker_decisions (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash);

CREATE TABLE IF NOT EXISTS agent_actions (
  action_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  action_type TEXT NOT NULL,
  action_json TEXT NOT NULL,
  action_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_logs_scenario_step ON email_logs (scenario_id, step);
CREATE INDEX IF NOT EXISTS idx_auth_logs_scenario_step ON auth_logs (scenario_id, step);
CREATE INDEX IF NOT EXISTS idx_netflow_scenario_step ON netflow (scenario_id, step);
CREATE INDEX IF NOT EXISTS idx_process_events_scenario_step ON process_events (scenario_id, step);
CREATE INDEX IF NOT EXISTS idx_alerts_scenario_step ON alerts (scenario_id, step);
