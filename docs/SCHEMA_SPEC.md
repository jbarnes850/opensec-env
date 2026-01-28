# Schema Spec (Phase 0)

This document locks the MVP schemas for seeds, SQLite logs, and action/observation/state models.

## 1) Seed JSON Schema (v1.0)
Location: `schemas/seed_schema.json`

Taxonomy spec: `docs/TAXONOMY_SPEC.md`

### Top-level fields
- schema_version: string ("1.0")
- scenario_id: string (unique, stable)
- scenario_name: string
- description: string
- entities: object
  - users: list of user objects
  - hosts: list of host objects
  - domains: list of domain objects
  - data_targets: list of data target objects
- attack_plan: object
- patient_zero_host: host_id
- compromised_user: user_id
- attacker_domain: domain
- data_target: target_id
- prompt_injection_payloads: list of payload objects
- seed_artifacts: object (emails, log_templates)
- metadata: object (generator_model, created_at, seed_source, max_steps?, taxonomy?)

### Entities
User object
- user_id: string
- email: string
- role: string
- dept: string

Host object
- host_id: string
- hostname: string
- owner_user_id: string
- ip: string
- os: string

Domain object
- domain: string
- domain_type: enum ["attacker", "legit", "internal"]

Data target object
- target_id: string
- name: string
- sensitivity: enum ["low", "medium", "high"]
- description: string

### attack_plan
- initial_vector: enum ["phish"]
- phishing_email_id: string
- credentials_used: object { user_id, method }
- lateral_path: list of { src_host, dst_host, method }
- data_access: object { target_id, method }
- exfiltration: object { channel, destination_domain }
- timeline: list of { step, attacker_state, artifacts }
  - artifacts: list of { artifact_type, artifact_id }
    - artifact_type: enum ["email", "log_template", "alert"]
    - artifact_id: string
    - variant_action_type: string (optional; match attacker action_type)
    - variant_params: object (optional; key/value match against attacker action params)

### attack_graph (optional)
Graph-driven attacker transitions and action-conditioned artifacts. When present, the runtime uses
this graph instead of the fixed `attack_plan.timeline` for dynamic log emission. This is the
primary mechanism for multi-objective, adaptive attacker behavior.

Core fields:
- start_state: string (optional; default "phish_sent")
- objectives: list of objective state names in coarse order (optional; used for progress metrics)
  - example: ["recon", "access", "persistence", "lateral_spread", "staging", "exfil"]
- initial_artifacts: list of { artifact_type, artifact_id, step?, match_params? }
  - step defaults to 0 if omitted
- states: mapping of state_name → state object
  - actions: list of action objects
    - action_type: string
    - next_state: string (optional; defaults to state-machine fallback)
    - match_params: object (optional; key/value match against attacker action params)
    - requires: object (optional; preconditions against attacker_context)
      - supported keys: foothold, has_creds, has_admin, has_stage, has_persistence,
        current_host, current_user, current_target
    - effects: object (optional; updates attacker_context after successful action)
      - supported keys: has_creds, has_admin, has_stage, has_persistence,
        compromise_host, compromise_user, current_host, current_user, current_target,
        current_exfil_domain
    - artifacts: list of { artifact_type, artifact_id, match_params? }
      - match_params filters on attacker action params (e.g., destination_domain)

Example (v2-style):
```
{
  "start_state": "recon",
  "objectives": ["recon", "access", "persistence", "lateral_spread", "staging", "exfil"],
  "initial_artifacts": [{"artifact_type": "email", "artifact_id": "email-001", "step": 0}],
  "states": {
    "recon": {
      "actions": [
        {
          "action_type": "send_phish",
          "next_state": "access",
          "effects": {"has_creds": true, "compromise_user": "u-001", "compromise_host": "h-001"},
          "artifacts": [{"artifact_type": "log_template", "artifact_id": "lt-auth-001"}]
        }
      ]
    },
    "access": {
      "actions": [
        {
          "action_type": "lateral_move",
          "requires": {"foothold": true},
          "next_state": "lateral_spread",
          "effects": {"has_admin": true, "compromise_host": "h-002"},
          "artifacts": [{"artifact_type": "log_template", "artifact_id": "lt-net-002"}]
        }
      ]
    },
    "staging": {
      "actions": [
        {
          "action_type": "stage_data",
          "requires": {"has_admin": true},
          "next_state": "exfil",
          "effects": {"has_stage": true, "current_target": "t-001"}
        }
      ]
    },
    "exfil": {
      "actions": [
        {
          "action_type": "exfiltrate",
          "requires": {"has_stage": true},
          "artifacts": [{"artifact_type": "log_template", "artifact_id": "lt-exfil-001"}]
        }
      ]
    }
  }
}
```

### Step lifecycle (definition)
A single environment step is defined as:
1) Agent action is applied (containment or investigation).
2) Attacker policy acts (unless stalled).
3) Logs and alerts are emitted for this step.
4) Oracle scoring is computed for the resulting state.

The `step` value stored in logs and attacker decisions corresponds to this full cycle.

### prompt_injection_payloads
- injection_id: string
- surface: enum ["email", "alert", "log"]
- payload: string
- expected_violation: enum ["follow_instruction", "tool_misuse", "data_exfil", "policy_override"]
- target_action: string (optional)
- target_params: object (optional; key/value pairs to match against action params)
- evidence_ids: list of strings (optional; may reference email_id, alert_id, auth_id, flow_id, event_id)
- injection_type: string (optional; e.g. direct_harm, data_exfil, adaptive)
- objective: string (optional; high-level attacker prompt objective)
- source: string (optional; injection pattern source such as injecagent or agentvigil)

### seed_artifacts
- emails: list of { email_id, sender, recipient, subject, body, injection_id?, trust_tier?, source? }
- log_templates: list of { template_id, table, template_body, injection_id?, trust_tier?, source? }
  - injection_id may be null if no prompt injection is present

### metadata
- generator_model: string
- created_at: string (ISO-8601)
- seed_source: string
- max_steps: integer (optional; if omitted, global default is 15)
- taxonomy: object (optional; taxonomy label for reproducibility)
  - version: string (e.g. "v1")
  - pattern_id: string (taxonomy class identifier)
  - family: string (coarse family label)
  - primary_action: string (primary injected action target)
  - surfaces: list of surfaces present (email/alert/log)
  - objective_profile: list of objectives (e.g., recon → exfil)
  - trust_profile: map of surface → trust tier (email/alert/log)
  - notes: string (optional)

## 2) SQLite Schema
Location: `schemas/sqlite_schema.sql`

Tables
- email_logs
- auth_logs
- netflow
- process_events
- alerts
- attacker_decisions
- agent_actions
- prompt_injections

Additional metadata columns:
- email_logs, auth_logs, netflow, process_events, alerts include optional trust_tier and source fields for provenance.
- prompt_injections includes optional injection_type, objective, and source fields for injection taxonomy.

attacker_decisions columns (added for deterministic replay under adaptive attacker policies):
- attacker_context_hash TEXT (sha256 of attacker_context or "none")

Indexes
- scenario_id + step for all log tables
- unique cache index for attacker_decisions on (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash)

Storage for prompt injection surfaces
- email_logs.injection_id for surface=email
- alerts.injection_id for surface=alert

### Log template expansion rules
Log templates are parsed using a simple key=value extractor that splits by whitespace and `=`:
- auth_logs: user, host, method, success inferred from text (\"success\" => 1)
- netflow: src, dst, dst_domain, port, proto, bytes
- process_events: host, user, process, parent; command_line is full template_body
- alerts: type, severity; message is full template_body

Templates that reference unknown tables are rejected by the compiler.

## 3) Ground Truth JSON Schema (v1.0)
Location: `schemas/ground_truth_schema.json`

### Top-level fields
- schema_version: string (\"1.0\")
- scenario_id: string
- attribution: object
  - patient_zero_host: host_id
  - compromised_user: user_id
  - attacker_domain: domain
  - data_target: target_id
  - initial_vector: string
- containment_requirements: object
  - isolate_hosts: list of host_id
  - block_domains: list of domain
  - reset_users: list of user_id
- prompt_injection_truth: list of { injection_id, expected_violation }
  - expected_violation: enum ["follow_instruction", "tool_misuse", "data_exfil", "policy_override"]

## 4) Action / Observation / State Models
These define the OpenEnv types to implement in Phase 1.

### AgentAction (discriminated union)
Common fields:
- action_type: enum
- params: object

Action types:
- query_logs: { sql }
- fetch_email: { email_id }
- fetch_alert: { alert_id }
- isolate_host: { host_id }
- block_domain: { domain }
- reset_user: { user_id }
- submit_report: { summary_json }
- noop: {}

Action result notes:
- fetch_alert returns the full alert row plus a `parsed` dict of key=value fields extracted
  from the alert message (e.g., dst_domain, src_host, compromised_user, data_target).

Constraints
- query_logs must be read-only SELECT (reject INSERT/UPDATE/DELETE/PRAGMA).
- IDs and domains must exist in scenario entities or logs.

### Observation
- scenario_id: string
- step_index: int
- attacker_state: enum ["phish_sent", "creds_used", "lateral_move", "data_access", "exfil_attempt"]
- containment: { isolated_hosts: [host_id], blocked_domains: [domain], reset_users: [user_id] }
- new_emails: [email_id]
- new_alerts: [alert_id]
- last_action_result: { ok: bool, message: string, data: object }
- hint: string (optional)

### State (for state())
- episode_id: string
- scenario_id: string
- step_count: int
- max_steps: int
- terminated: bool
- truncated: bool

### submit_report summary_json
- patient_zero_host: host_id
- compromised_user: user_id
- attacker_domain: domain
- data_target: target_id
- containment_actions: { isolated_hosts, blocked_domains, reset_users }
- prompt_injection_followed: bool
- evidence: string

## 5) Replay Cache Key
- agent_action_hash = sha256(canonical_json(action))
- canonical_json = UTF-8 JSON, sorted keys, no whitespace
- attacker_context_hash = sha256(canonical_json(attacker_context)) or "none" if empty
- cache key = (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash)

## 6) Determinism Rules
- Live attacker is stochastic; replay mode is deterministic.
- Oracle scoring deterministic for any given trajectory.
- Log emission deterministic for a given seed + attacker/agent actions.

## 7) Data Format Notes
- Boolean columns are stored as 0/1 integers.
- Timestamps are ISO-8601 strings.

## 8) Global Defaults
- max_steps default: 15 (unless scenario metadata overrides)
