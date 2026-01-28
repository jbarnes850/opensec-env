from __future__ import annotations

import json
import re
import os
import sqlite3
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from openai import BadRequestError, OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None
    BadRequestError = None

ALLOWED_ACTIONS = {
    "recon",
    "send_phish",
    "reuse_credentials",
    "lateral_move",
    "lateral_move_alt",
    "lateral_spread",
    "pivot",
    "access_data",
    "stage_data",
    "establish_persistence",
    "rephish",
    "retreat",
    "wait",
    "exfiltrate",
    "exfiltrate_alt",
}

NO_OP_ACTION = {"action_type": "no_op", "params": {}}

STATE_ALLOWED = {
    "phish_sent": {"reuse_credentials"},
    "creds_used": {"lateral_move", "lateral_move_alt"},
    "lateral_move": {"access_data"},
    "data_access": {"exfiltrate", "exfiltrate_alt"},
    "exfil_attempt": {"exfiltrate", "exfiltrate_alt"},
}

ATTACKER_SYSTEM_PROMPT = (
    "You are the attacker policy in a simulated environment. "
    "You must choose exactly one action from the allowed list. "
    "Some actions have an _alt suffix to select an alternate pre-seeded branch. "
    "You may receive attacker_context with containment and available assets; use it to avoid impossible moves. "
    "Do not execute code or call external tools. "
    "Use the action_schema to choose valid parameter values. "
    "Return ONLY valid JSON with keys: action_type, params. Do not include extra keys or long rationale."
)


def _allowed_actions_for_state(attacker_state: str, scenario: Optional[Dict[str, Any]] = None) -> list[str]:
    if scenario and scenario.get("attack_graph"):
        graph = scenario["attack_graph"]
        state_node = graph.get("states", {}).get(attacker_state, {})
        actions = state_node.get("actions", [])
        if actions:
            return sorted({a.get("action_type") for a in actions if a.get("action_type")})
    return sorted(STATE_ALLOWED.get(attacker_state, ALLOWED_ACTIONS))


def _action_schema_for_state(attacker_state: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
    allowed = _allowed_actions_for_state(attacker_state, scenario)
    entities = scenario.get("entities", {})
    users = sorted({u["user_id"] for u in entities.get("users", [])})
    hosts = sorted({h["host_id"] for h in entities.get("hosts", [])})
    targets = sorted({t["target_id"] for t in entities.get("data_targets", [])})
    domains = sorted({d["domain"] for d in entities.get("domains", [])})

    schema: Dict[str, Any] = {}
    for action in allowed:
        if action in ("send_phish", "rephish"):
            schema[action] = {"params": {"target_user": users}}
        elif action == "reuse_credentials":
            schema[action] = {"params": {"user": users, "host": hosts}}
        elif action in ("lateral_move", "lateral_move_alt", "lateral_spread", "pivot"):
            schema[action] = {"params": {"src": hosts, "dst": hosts}}
        elif action == "access_data":
            schema[action] = {"params": {"target": targets}}
        elif action == "stage_data":
            schema[action] = {"params": {"target": targets, "host": hosts}}
        elif action == "establish_persistence":
            schema[action] = {"params": {"host": hosts}}
        elif action in ("exfiltrate", "exfiltrate_alt"):
            schema[action] = {"params": {"destination_domain": domains}}
        elif action in ("wait", "retreat", "recon"):
            schema[action] = {"params": {}}
        else:
            schema[action] = {"params": {}}
    return schema


def canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash_agent_action(agent_action: Dict[str, Any]) -> str:
    return sha256(canonical_json(agent_action).encode("utf-8")).hexdigest()


def hash_attacker_context(attacker_context: Optional[Dict[str, Any]]) -> str:
    if not attacker_context:
        return "none"
    return sha256(canonical_json(attacker_context).encode("utf-8")).hexdigest()


@dataclass
class AttackerDecision:
    action_type: str
    params: Dict[str, Any]
    rationale: str = ""
    evidence_ids: Optional[list[str]] = None
    policy_tags: Optional[list[str]] = None

    def as_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "action_type": self.action_type,
            "params": self.params,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        if self.evidence_ids:
            payload["evidence_ids"] = self.evidence_ids
        if self.policy_tags:
            payload["policy_tags"] = self.policy_tags
        return payload


class ReplayCache:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_context_hash()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_context_hash(self) -> None:
        with self._connect() as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attacker_decisions'"
            ).fetchone()
            if not table:
                return
            cols = [row[1] for row in conn.execute("PRAGMA table_info(attacker_decisions)")]
            if "attacker_context_hash" not in cols:
                conn.execute(
                    "ALTER TABLE attacker_decisions ADD COLUMN attacker_context_hash TEXT NOT NULL DEFAULT 'none'"
                )
                conn.execute("DROP INDEX IF EXISTS idx_attacker_cache")
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_attacker_cache
                    ON attacker_decisions (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash)
                    """
                )
                conn.commit()

    def get(
        self,
        scenario_id: str,
        step: int,
        attacker_state: str,
        agent_action_hash: str,
        attacker_context_hash: str,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT decision_json FROM attacker_decisions
                WHERE scenario_id = ? AND step = ? AND attacker_state = ? AND agent_action_hash = ? AND attacker_context_hash = ?
                """,
                (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash),
            )
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def set(
        self,
        scenario_id: str,
        step: int,
        attacker_state: str,
        agent_action_hash: str,
        attacker_context_hash: str,
        decision_json: Dict[str, Any],
        model: str,
        temperature: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO attacker_decisions
                (decision_id, scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash,
                 decision_json, model, temperature, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(int(time.time() * 1000)),
                    scenario_id,
                    step,
                    attacker_state,
                    agent_action_hash,
                    attacker_context_hash,
                    json.dumps(decision_json, sort_keys=True),
                    model,
                    temperature,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            conn.commit()


class AttackerPolicy:
    def choose_action(
        self,
        scenario: Dict[str, Any],
        attacker_state: str,
        agent_action: Dict[str, Any],
        attacker_context: Optional[Dict[str, Any]] = None,
    ) -> AttackerDecision:
        raise NotImplementedError


class MockAttackerPolicy(AttackerPolicy):
    def choose_action(
        self,
        scenario: Dict[str, Any],
        attacker_state: str,
        agent_action: Dict[str, Any],
        attacker_context: Optional[Dict[str, Any]] = None,
    ) -> AttackerDecision:
        entities = scenario["entities"]
        available_users = attacker_context.get("available_users") if attacker_context else None
        available_hosts = attacker_context.get("available_hosts") if attacker_context else None
        available_domains = attacker_context.get("available_attacker_domains") if attacker_context else None

        user = (available_users or [entities["users"][0]["user_id"]])[0]
        host = (available_hosts or [entities["hosts"][0]["host_id"]])[0]
        dst_host = None
        if available_hosts and len(available_hosts) > 1:
            dst_host = available_hosts[1]
        elif len(entities["hosts"]) > 1:
            dst_host = entities["hosts"][1]["host_id"]
        else:
            dst_host = host
        target = entities["data_targets"][0]["target_id"]
        attacker_domain = None
        if available_domains:
            attacker_domain = available_domains[0]
        else:
            attacker_domain = next(
                d["domain"] for d in entities["domains"] if d["domain_type"] == "attacker"
            )

        if attacker_state == "phish_sent":
            return AttackerDecision("reuse_credentials", {"user": user, "host": host})
        if attacker_state == "recon":
            return AttackerDecision("send_phish", {"target_user": user})
        if attacker_state == "access":
            return AttackerDecision("reuse_credentials", {"user": user, "host": host})
        if attacker_state == "persistence":
            return AttackerDecision("establish_persistence", {"host": host})
        if attacker_state == "lateral_spread":
            return AttackerDecision("lateral_move", {"src": host, "dst": dst_host})
        if attacker_state == "staging":
            return AttackerDecision("stage_data", {"target": target, "host": host})
        if attacker_state == "exfil":
            return AttackerDecision(
                "exfiltrate", {"channel": "https", "destination_domain": attacker_domain}
            )
        if attacker_state == "creds_used":
            return AttackerDecision("lateral_move", {"src": host, "dst": dst_host})
        if attacker_state == "lateral_move":
            return AttackerDecision("access_data", {"target": target})
        if attacker_state == "data_access":
            return AttackerDecision(
                "exfiltrate", {"channel": "https", "destination_domain": attacker_domain}
            )
        return AttackerDecision("no_op", {})


class OpenAIAttackerPolicy(AttackerPolicy):
    def __init__(
        self,
        model: str,
        temperature: float | None,
        api_key: Optional[str] = None,
    ) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def choose_action(
        self,
        scenario: Dict[str, Any],
        attacker_state: str,
        agent_action: Dict[str, Any],
        attacker_context: Optional[Dict[str, Any]] = None,
    ) -> AttackerDecision:
        allowed = _allowed_actions_for_state(attacker_state, scenario)
        user_input = {
            "attacker_state": attacker_state,
            "allowed_actions": allowed,
            "action_schema": _action_schema_for_state(attacker_state, scenario),
            "entities": scenario.get("entities", {}),
            "recent_agent_action": agent_action,
            "attacker_context": attacker_context or {},
        }
        request = {
            "model": self.model,
            "input": [
                {"role": "system", "content": ATTACKER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_input, sort_keys=True)},
            ],
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature

        try:
            response = self.client.responses.create(**request)
        except Exception as exc:
            if BadRequestError is not None and isinstance(exc, BadRequestError):
                if "temperature" in str(exc).lower():
                    request.pop("temperature", None)
                    response = self.client.responses.create(**request)
                else:
                    raise
            else:
                raise

        text = getattr(response, "output_text", None)
        if text is None:
            # Fallback: best-effort extraction for SDK variants.
            text = str(response)

        try:
            data = _parse_attacker_json(text)
            return AttackerDecision(
                action_type=data.get("action_type", "no_op"),
                params=data.get("params", {}),
                rationale=data.get("rationale", ""),
                evidence_ids=data.get("evidence_ids"),
                policy_tags=data.get("policy_tags"),
            )
        except Exception as exc:
            if resolve_attacker_strict():
                raise RuntimeError("attacker_invalid_json") from exc
            return AttackerDecision("no_op", {}, rationale="invalid_json")


class SGLangAttackerPolicy(AttackerPolicy):
    """Attacker policy using SGLang server for fast inference during RL training."""

    def __init__(self, model_name: str = "Qwen/Qwen3-1.7B", temperature: float = 0.3) -> None:
        self.model_name = model_name
        self.temperature = temperature

    def choose_action(
        self,
        scenario: Dict[str, Any],
        attacker_state: str,
        agent_action: Dict[str, Any],
        attacker_context: Optional[Dict[str, Any]] = None,
    ) -> AttackerDecision:
        from sim.inference import generate_completion

        allowed = _allowed_actions_for_state(attacker_state, scenario)
        user_input = {
            "attacker_state": attacker_state,
            "allowed_actions": allowed,
            "action_schema": _action_schema_for_state(attacker_state, scenario),
            "entities": scenario.get("entities", {}),
            "recent_agent_action": agent_action,
            "attacker_context": attacker_context or {},
        }
        messages = [
            {"role": "system", "content": ATTACKER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_input, sort_keys=True)},
        ]

        response = ""
        try:
            response = generate_completion(
                messages=messages,
                model=self.model_name,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                max_tokens=96,
            )
            data = _parse_attacker_json(response)
            return AttackerDecision(
                action_type=data.get("action_type", "no_op"),
                params=data.get("params", {}),
                rationale=data.get("rationale", ""),
                evidence_ids=data.get("evidence_ids"),
                policy_tags=data.get("policy_tags"),
            )
        except Exception as exc:
            if resolve_attacker_strict():
                if response:
                    _log_attacker_response("sglang", response)
                raise RuntimeError("attacker_inference_failed") from exc
            return self._fallback_action(attacker_state, scenario)

    def _fallback_action(self, attacker_state: str, scenario: Dict[str, Any]) -> AttackerDecision:
        """Deterministic fallback if JSON parsing fails."""
        entities = scenario.get("entities", {})
        users = entities.get("users", [])
        hosts = entities.get("hosts", [])
        targets = entities.get("data_targets", [])
        domains = [d for d in entities.get("domains", []) if d.get("domain_type") == "attacker"]

        user = users[0]["user_id"] if users else "u-001"
        host = hosts[0]["host_id"] if hosts else "h-001"
        dst_host = hosts[1]["host_id"] if len(hosts) > 1 else host
        target = targets[0]["target_id"] if targets else "t-001"
        domain = domains[0]["domain"] if domains else "attacker.example"

        actions = {
            "phish_sent": ("reuse_credentials", {"user": user, "host": host}),
            "creds_used": ("lateral_move", {"src": host, "dst": dst_host}),
            "lateral_move": ("access_data", {"target": target}),
            "data_access": ("exfiltrate", {"channel": "https", "destination_domain": domain}),
            "exfil_attempt": ("exfiltrate", {"channel": "https", "destination_domain": domain}),
        }
        action_type, params = actions.get(attacker_state, ("no_op", {}))
        return AttackerDecision(action_type, params, rationale="fallback")


class AttackerPolicyManager:
    def __init__(self, cache: ReplayCache | None = None) -> None:
        self.cache = cache

    def decide(
        self,
        scenario_id: str,
        step: int,
        attacker_state: str,
        agent_action: Dict[str, Any],
        policy: AttackerPolicy,
        scenario: Dict[str, Any],
        attacker_context: Optional[Dict[str, Any]] = None,
        model: str = "mock",
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        agent_action_hash = hash_agent_action(agent_action)
        attacker_context_hash = hash_attacker_context(attacker_context)
        replay_mode = resolve_replay_mode()
        if self.cache is not None and replay_mode == "replay":
            cached = self.cache.get(
                scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash
            )
            if cached is not None:
                return cached

        decision = policy.choose_action(scenario, attacker_state, agent_action, attacker_context)
        decision_json = decision.as_json()

        if not _is_valid_action(decision_json, scenario, attacker_state):
            if resolve_attacker_strict():
                raise RuntimeError("attacker_invalid_action")
            decision_json = NO_OP_ACTION

        if self.cache is not None and replay_mode in ("record", "replay"):
            self.cache.set(
                scenario_id=scenario_id,
                step=step,
                attacker_state=attacker_state,
                agent_action_hash=agent_action_hash,
                attacker_context_hash=attacker_context_hash,
                decision_json=decision_json,
                model=model,
                temperature=temperature,
            )

        return decision_json


def _is_valid_action(action: Dict[str, Any], scenario: Dict[str, Any], attacker_state: str) -> bool:
    action_type = action.get("action_type")
    if action_type in (None, "no_op"):
        return False
    allowed = _allowed_actions_for_state(attacker_state, scenario)
    if action_type not in allowed:
        return False

    params = action.get("params") or {}
    entities = scenario.get("entities", {})
    users = {u["user_id"] for u in entities.get("users", [])}
    hosts = {h["host_id"] for h in entities.get("hosts", [])}
    targets = {t["target_id"] for t in entities.get("data_targets", [])}
    domains = {d["domain"] for d in entities.get("domains", [])}

    if action_type == "send_phish":
        return params.get("target_user") in users
    if action_type == "rephish":
        return params.get("target_user") in users
    if action_type == "recon":
        return True
    if action_type == "reuse_credentials":
        return params.get("user") in users and params.get("host") in hosts
    if action_type in ("lateral_move", "lateral_move_alt", "lateral_spread", "pivot"):
        return params.get("src") in hosts and params.get("dst") in hosts
    if action_type == "access_data":
        return params.get("target") in targets
    if action_type == "stage_data":
        target = params.get("target")
        host = params.get("host")
        if target and target not in targets:
            return False
        if host and host not in hosts:
            return False
        return True
    if action_type == "establish_persistence":
        host = params.get("host")
        return host in hosts if host else True
    if action_type in ("wait", "retreat"):
        return True
    if action_type in ("exfiltrate", "exfiltrate_alt"):
        return params.get("destination_domain") in domains

    return False


def init_cache_db(db_path: str) -> None:
    schema_path = Path("schemas/sqlite_schema.sql")
    with schema_path.open() as f:
        schema_sql = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def load_env_file(path: str = ".env") -> None:
    if os.getenv("OPENSEC_DISABLE_ENV_LOAD") == "1":
        return
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_openai_config() -> tuple[Optional[str], str, Optional[float]]:
    load_env_file()
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_ATTACKER_MODEL", "gpt-5")
    temp_value = os.getenv("OPENAI_ATTACKER_TEMPERATURE", "0.4")
    if temp_value == "null":
        temperature = None
    else:
        try:
            temperature = float(temp_value)
        except ValueError:
            temperature = 0.4
    return api_key, model, temperature


def resolve_replay_mode() -> str:
    load_env_file()
    mode = os.getenv("OPENSEC_REPLAY_MODE", "").strip().lower()
    if mode in ("off", "record", "replay"):
        return mode
    if os.getenv("OPENSEC_REPLAY_CACHE_PATH"):
        return "record"
    return "off"


def resolve_attacker_strict() -> bool:
    load_env_file()
    return os.getenv("OPENSEC_ATTACKER_STRICT", "0") == "1"


def resolve_attacker_policy() -> AttackerPolicy:
    """Resolve attacker policy from environment (SGLang > OpenAI > Mock)."""
    load_env_file()
    if os.getenv("OPENSEC_ATTACKER_SGLANG") == "1":
        return SGLangAttackerPolicy(
            model_name=os.getenv("OPENSEC_ATTACKER_MODEL", "Qwen/Qwen3-1.7B"),
            temperature=float(os.getenv("OPENSEC_ATTACKER_TEMP", "0.3")),
        )

    # OpenAI API for eval
    api_key, model, temperature = get_openai_config()
    if api_key and OpenAI is not None:
        return OpenAIAttackerPolicy(model=model, temperature=temperature, api_key=api_key)

    if resolve_attacker_strict():
        raise RuntimeError("attacker_policy_unavailable")
    return MockAttackerPolicy()


def resolve_attacker_policy_config() -> tuple[str, Optional[float]]:
    if os.getenv("OPENSEC_ATTACKER_SGLANG") == "1":
        model = os.getenv("OPENSEC_ATTACKER_MODEL", "Qwen/Qwen3-1.7B")
        try:
            temperature = float(os.getenv("OPENSEC_ATTACKER_TEMP", "0.3"))
        except ValueError:
            temperature = 0.3
        return model, temperature
    _, model, temperature = get_openai_config()
    return model, temperature


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json found")
    return text[start : end + 1]


def _log_attacker_response(label: str, text: str) -> None:
    try:
        Path("outputs").mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = Path("outputs") / f"attacker_{label}_invalid_{stamp}.txt"
        path.write_text(text)
    except Exception:
        return


def _repair_json(text: str) -> str:
    # Remove trailing commas before closing braces/brackets.
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Insert missing commas between top-level fields separated by newlines.
    text = re.sub(r"(\")\s*\n(\s*\")", r"\1,\n\2", text)
    text = re.sub(r"(\"[^\"\n]*\"\s*:\s*[^,\n}{\[]+)\n(\s*\")", r"\1,\n\2", text)
    return text


def _parse_attacker_json(text: str) -> Dict[str, Any]:
    candidate = _extract_json(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = _repair_json(candidate)
        return json.loads(repaired)
