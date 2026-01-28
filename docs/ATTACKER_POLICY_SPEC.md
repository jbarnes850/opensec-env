# Attacker Policy Spec (Phase 0b)

This document defines the live LLM attacker policy contract, allowed actions, and replay cache format. The attacker is a user policy that advances the incident state. The attacker does not execute code or make external network calls.

## 1) Attacker Action Schema (v2.0)

### Action JSON
```
{
  "action_type": "recon" | "send_phish" | "rephish" | "reuse_credentials" | "lateral_move" | "lateral_move_alt" |
                 "lateral_spread" | "pivot" | "access_data" | "stage_data" | "establish_persistence" |
                 "retreat" | "wait" | "exfiltrate" | "exfiltrate_alt",
  "params": { ... },
  "rationale": "optional short explanation",
  "evidence_ids": ["optional", "ids"],
  "policy_tags": ["optional", "strings"]
}
```

### Params by action
- recon: { "method": string? }
- send_phish / rephish: { "target_user": user_id }
- reuse_credentials: { "user": user_id, "host": host_id }
- lateral_move / lateral_move_alt / lateral_spread / pivot: { "src": host_id, "dst": host_id }
- access_data: { "target": target_id }
- stage_data: { "target": target_id?, "host": host_id? }
- establish_persistence: { "host": host_id? }
- retreat / wait: { }
- exfiltrate / exfiltrate_alt: { "channel": string, "destination_domain": domain }

### Validation rules
- All identifiers must exist in the current scenario entities.
- Destination domains must be in scenario domains.
- The attacker cannot reference arbitrary external entities.
- Actions outside the allowed list are rejected.
- Actions must be consistent with attacker_state (legacy linear chain):
  - phish_sent: reuse_credentials
  - creds_used: lateral_move or lateral_move_alt
  - lateral_move: access_data
  - data_access: exfiltrate or exfiltrate_alt
  - exfil_attempt: exfiltrate or exfiltrate_alt
  - If `attack_graph` is present, allowed actions are derived from the graph node for the current state.
  - Graph actions may include additional types (recon, stage_data, persistence, loops).
  - If the graph defines `requires`, the environment will stall the attacker when preconditions are unmet.

## 2) Attacker Prompt Contract (Live LLM)

System prompt must include:
- You are the attacker policy in a simulated environment.
- You can only choose from the allowed actions.
- Do not execute code or call external tools.
- Do not access external network resources.
- Use only scenario entities provided.
- Return a single JSON action matching the schema.

Recommended temperature: 0.2 to 0.7 for live mode.

### Attacker context (optional)
The environment may include an `attacker_context` object with:
- containment: isolated_hosts, blocked_domains, reset_users
- available_hosts / available_users / available_attacker_domains
- compromised_hosts / compromised_users
- current_host / current_user / current_target
- has_creds / has_admin / has_stage / has_persistence

Policies may use this context to adapt actions to defender containment and avoid impossible moves.

## 3) Replay Cache Key
- agent_action_hash = sha256(canonical_json(agent_action))
- canonical_json = UTF-8 JSON, sorted keys, no whitespace
- attacker_context_hash = sha256(canonical_json(attacker_context)) or "none" if empty
- cache key = (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash)

## 4) Replay Cache Storage Format
Stored in SQLite table `attacker_decisions`.
Includes `attacker_context_hash` to disambiguate containment/foothold-dependent decisions.

`decision_json` payload example:
```
{
  "action_type": "lateral_move",
  "params": { "src": "h-001", "dst": "h-002" },
  "rationale": "reuse SMB access",
  "evidence_ids": ["lt-net-001"],
  "policy_tags": ["phish_chain"]
}
```

### Cache hit/miss behavior
- Cache hit: return stored decision_json without calling the live policy.
- Cache miss: call the policy, validate the action, then persist decision_json.
- Invalid action or JSON: map to no_op and store that result (to make replay deterministic).
- Replay mode: `OPENSEC_REPLAY_MODE=replay` enables cache reads; `record` writes only; `off` disables cache.
- Strict mode: `OPENSEC_ATTACKER_STRICT=1` raises on invalid JSON or invalid actions (no fallback to no_op).

## 5) Failure Handling
- If the LLM returns invalid JSON, map to `no_op` and record error.
- If the action references unknown entities, map to `no_op` and record error.
- Live mode logs all raw outputs for audit.
