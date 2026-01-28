from __future__ import annotations

import os
import sqlite3
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sim.attacker_policy import (
    AttackerPolicyManager,
    ReplayCache,
    init_cache_db,
    resolve_attacker_policy,
    resolve_attacker_policy_config,
    resolve_replay_mode,
)
from sim.attacker_state_machine import (
    AttackerContext,
    ContainmentActions,
    ScenarioContext,
    advance_state,
    apply_attacker_action,
)
from sim.log_compiler import compile_seed, emit_artifact

from oracle.scoring import containment_to_dict, score_report
from oracle.verifier import detect_injection_violations

from .models import ActionResult, AgentAction, ContainmentState, EpisodeState, Observation, StepResult


class OpenSecEnvironment:
    def __init__(
        self,
        scenario_id: str = "seed-001",
        seed_path: str = "data/seeds/sample_seed.json",
        sqlite_dir: str = "data/sqlite",
        max_steps: int = 15,
        mask_injections: bool = False,
    ) -> None:
        self.scenario_id = scenario_id
        self.max_steps = max_steps
        self.seed_path = seed_path
        self.sqlite_dir = sqlite_dir
        self.mask_injections = mask_injections
        self.episode_id = ""
        self.step_count = 0
        self.attacker_state = "phish_sent"
        self.attacker_context = AttackerContext()
        self.containment = ContainmentState()
        self.scenario: Optional[Dict[str, Any]] = None
        self.db_path: Optional[str] = None
        cache_path = os.getenv("OPENSEC_REPLAY_CACHE_PATH")
        if cache_path and resolve_replay_mode() != "off":
            init_cache_db(cache_path)
            self.cache = ReplayCache(cache_path)
        else:
            self.cache = None
        self.policy_manager = AttackerPolicyManager(cache=self.cache)
        self.policy = resolve_attacker_policy()
        self.ground_truth: Optional[Dict[str, Any]] = None
        self.seen_evidence_ids: Set[str] = set()
        self.content_evidence_ids: Set[str] = set()
        self.injection_violations: List[str] = []

    def reset(self) -> StepResult:
        self.episode_id = str(uuid.uuid4())
        self.step_count = 0
        self.attacker_state = "phish_sent"
        self.attacker_context = AttackerContext()
        self.containment = ContainmentState()
        self.seen_evidence_ids = set()
        self.content_evidence_ids = set()
        self.injection_violations = []
        self._load_scenario()
        if self.scenario and self.scenario.get("attack_graph", {}).get("start_state"):
            self.attacker_state = self.scenario["attack_graph"]["start_state"]
        if self.mask_injections and self.scenario:
            self.scenario["prompt_injection_payloads"] = []
        self._init_db()

        new_emails = self._emails_for_step(0)
        new_alerts = self._alerts_for_step(0)
        self._record_evidence(new_emails, new_alerts)

        state = self.state()
        observation = Observation(
            scenario_id=self.scenario_id,
            step_index=self.step_count,
            attacker_state=self.attacker_state,
            containment=self.containment,
            new_emails=new_emails,
            new_alerts=new_alerts,
            evidence_seen_ids=sorted(self.seen_evidence_ids),
            evidence_content_ids=sorted(self.content_evidence_ids),
            last_action_result=ActionResult(ok=True, message="reset", data={}),
            hint="Environment ready",
            done=False,
            reward=None,
            metadata={"info": {}, "state": state.model_dump()},
        )

        return StepResult(
            observation=observation,
            reward=0.0,
            done=False,
            info={},
            state=state,
        )

    def step(self, action: AgentAction) -> StepResult:
        if self.scenario is None or self.db_path is None:
            self._load_scenario()
            self._init_db()

        result = self.apply_action(action)

        violations = detect_injection_violations(
            action.model_dump(),
            self.content_evidence_ids,
            self.scenario.get("prompt_injection_payloads", []),
        )
        if violations:
            self.injection_violations.extend(violations)

        model, temperature = resolve_attacker_policy_config()
        attacker_context_payload = self._attacker_policy_context()
        attacker_action = self.policy_manager.decide(
            scenario_id=self.scenario_id,
            step=self.step_count,
            attacker_state=self.attacker_state,
            agent_action=action.model_dump(),
            policy=self.policy,
            scenario=self.scenario,
            attacker_context=attacker_context_payload,
            model=model,
            temperature=temperature,
        )

        prior_state = self.attacker_state
        ctx = ScenarioContext(
            attacker_domain=self.scenario["attacker_domain"],
            patient_zero_host=self.scenario["patient_zero_host"],
            compromised_user=self.scenario["compromised_user"],
        )
        containment = ContainmentActions(
            isolated_hosts=self.containment.isolated_hosts,
            blocked_domains=self.containment.blocked_domains,
            reset_users=self.containment.reset_users,
        )
        advance = advance_state(
            self.attacker_state,
            containment,
            ctx,
            attacker_action=attacker_action,
            attacker_context=self.attacker_context,
            attack_graph=self.scenario.get("attack_graph"),
        )
        self.attacker_state = advance.next_state

        self.step_count += 1
        if self._uses_attack_graph():
            self._emit_action_artifacts(self.step_count, prior_state, attacker_action)
        else:
            self._emit_variant_artifacts(self.step_count, attacker_action)
        if not advance.stalled:
            effects = None
            if advance.matched_action:
                effects = advance.matched_action.get("effects")
            apply_attacker_action(self.attacker_context, attacker_action, effects=effects)
        done = self.step_count >= self.max_steps

        new_emails = self._emails_for_step(self.step_count)
        new_alerts = self._alerts_for_step(self.step_count)
        self._record_evidence(new_emails, new_alerts)

        reward = 0.0
        if action.action_type == "submit_report" and self.ground_truth is not None:
            report = action.params.get("summary_json", {})
            executed_containment = containment_to_dict(self.containment)
            score = score_report(
                report, self.ground_truth, self.step_count, self.injection_violations,
                executed_containment=executed_containment,
            )
            reward = score.reward

        info = {
            "action_type": action.action_type,
            "attacker_action": attacker_action,
            "attacker_stalled": advance.stalled,
            "attacker_reason": advance.reason,
            "injection_violations": list(self.injection_violations),
        }
        state = self.state()
        observation = Observation(
            scenario_id=self.scenario_id,
            step_index=self.step_count,
            attacker_state=self.attacker_state,
            containment=self.containment,
            new_emails=new_emails,
            new_alerts=new_alerts,
            evidence_seen_ids=sorted(self.seen_evidence_ids),
            evidence_content_ids=sorted(self.content_evidence_ids),
            last_action_result=ActionResult(ok=True, message=action.action_type, data=result),
            done=done,
            reward=reward,
            metadata={"info": info, "state": state.model_dump()},
        )

        return StepResult(
            observation=observation,
            reward=reward,
            done=done,
            info=info,
            state=state,
        )

    def _emit_variant_artifacts(self, step: int, attacker_action: Dict[str, Any]) -> None:
        if self.scenario is None or self.db_path is None:
            return
        action_type = attacker_action.get("action_type")
        action_params = attacker_action.get("params", {})
        if not action_type:
            return
        timeline = self.scenario["attack_plan"]["timeline"]
        log_templates = {t["template_id"]: t for t in self.scenario["seed_artifacts"]["log_templates"]}
        for item in timeline:
            if item["step"] != step:
                continue
            for art in item["artifacts"]:
                variant_action = art.get("variant_action_type")
                if not variant_action:
                    continue
                if variant_action != action_type:
                    continue
                variant_params = art.get("variant_params") or {}
                if variant_params:
                    if any(action_params.get(k) != v for k, v in variant_params.items()):
                        continue
                with sqlite3.connect(self.db_path) as conn:
                    emit_artifact(conn, self.scenario, step, art, log_templates, allow_variant=True)
                    conn.commit()

    def _emit_action_artifacts(
        self,
        step: int,
        prior_state: str,
        attacker_action: Dict[str, Any],
    ) -> None:
        if self.scenario is None or self.db_path is None:
            return
        action_type = attacker_action.get("action_type")
        if not action_type or action_type == "no_op":
            return
        graph = self.scenario.get("attack_graph") or {}
        states = graph.get("states", {})
        node = states.get(prior_state, {})
        actions = node.get("actions", [])
        if not actions:
            return
        log_templates = {t["template_id"]: t for t in self.scenario["seed_artifacts"]["log_templates"]}
        params = attacker_action.get("params") or {}
        for action in actions:
            if action.get("action_type") != action_type:
                continue
            match_params = action.get("match_params") or {}
            if match_params:
                if any(params.get(k) != v for k, v in match_params.items()):
                    continue
            for art in action.get("artifacts", []):
                art_match = art.get("match_params") or {}
                if art_match:
                    if any(params.get(k) != v for k, v in art_match.items()):
                        continue
                with sqlite3.connect(self.db_path) as conn:
                    emit_artifact(conn, self.scenario, step, art, log_templates, allow_variant=True)
                    conn.commit()

    def _uses_attack_graph(self) -> bool:
        return bool(self.scenario and self.scenario.get("attack_graph"))

    def _attacker_policy_context(self) -> Dict[str, Any]:
        entities = (self.scenario or {}).get("entities", {})
        hosts = [h["host_id"] for h in entities.get("hosts", []) if h.get("host_id")]
        users = [u["user_id"] for u in entities.get("users", []) if u.get("user_id")]
        attacker_domains = [
            d["domain"]
            for d in entities.get("domains", [])
            if d.get("domain_type") == "attacker"
        ]
        available_hosts = [h for h in hosts if h not in self.containment.isolated_hosts]
        available_users = [u for u in users if u not in self.containment.reset_users]
        available_domains = [
            d for d in attacker_domains if d not in self.containment.blocked_domains
        ]
        return {
            "step": self.step_count,
            "containment": {
                "isolated_hosts": sorted(self.containment.isolated_hosts),
                "blocked_domains": sorted(self.containment.blocked_domains),
                "reset_users": sorted(self.containment.reset_users),
            },
            "available_hosts": sorted(available_hosts),
            "available_users": sorted(available_users),
            "available_attacker_domains": sorted(available_domains),
            "compromised_hosts": sorted(self.attacker_context.compromised_hosts),
            "compromised_users": sorted(self.attacker_context.compromised_users),
            "current_host": self.attacker_context.current_host,
            "current_user": self.attacker_context.current_user,
            "current_target": self.attacker_context.current_target,
            "current_exfil_domain": self.attacker_context.current_exfil_domain,
            "has_creds": self.attacker_context.has_creds,
            "has_admin": self.attacker_context.has_admin,
            "has_stage": self.attacker_context.has_stage,
            "has_persistence": self.attacker_context.has_persistence,
        }

    def state(self) -> EpisodeState:
        return EpisodeState(
            episode_id=self.episode_id,
            scenario_id=self.scenario_id,
            step_count=self.step_count,
            max_steps=self.max_steps,
            terminated=False,
            truncated=self.step_count >= self.max_steps,
        )

    def apply_action(self, action: AgentAction) -> Dict[str, Any]:
        if action.action_type == "isolate_host":
            host_id = action.params.get("host_id")
            if host_id and host_id not in self.containment.isolated_hosts:
                self.containment.isolated_hosts.append(host_id)
            return {"ok": True, "isolated_host": host_id}
        if action.action_type == "block_domain":
            domain = action.params.get("domain")
            if domain and domain not in self.containment.blocked_domains:
                self.containment.blocked_domains.append(domain)
            return {"ok": True, "blocked_domain": domain}
        if action.action_type == "reset_user":
            user_id = action.params.get("user_id")
            if user_id and user_id not in self.containment.reset_users:
                self.containment.reset_users.append(user_id)
            return {"ok": True, "reset_user": user_id}
        if action.action_type == "query_logs":
            sql = action.params.get("sql", "")
            if not self._is_readonly_select(sql):
                return {"ok": False, "error": "only SELECT queries are allowed"}
            try:
                rows = self._query_logs(sql)
            except sqlite3.OperationalError as exc:
                return {"ok": False, "error": str(exc)}
            self._record_content_evidence_from_rows(rows)
            return {"ok": True, "rows": rows}
        if action.action_type == "fetch_email":
            email_id = action.params.get("email_id")
            if not email_id:
                return {"ok": False, "error": "email_id required"}
            self.content_evidence_ids.add(email_id)
            email = self._fetch_email(email_id)
            return {"ok": True, "email_id": email_id, "email": email}
        if action.action_type == "fetch_alert":
            alert_id = action.params.get("alert_id")
            if not alert_id:
                return {"ok": False, "error": "alert_id required"}
            self.content_evidence_ids.add(alert_id)
            alert = self._fetch_alert(alert_id)
            parsed = self._parse_alert_fields(alert.get("message", "")) if alert else {}
            return {"ok": True, "alert_id": alert_id, "alert": alert, "parsed": parsed}
        return {"ok": True}

    def _load_scenario(self) -> None:
        path = Path(self.seed_path)
        self.scenario = json_load(path)
        self.scenario_id = self.scenario["scenario_id"]
        self.max_steps = self.scenario.get("metadata", {}).get("max_steps", self.max_steps)
        gt_path = _resolve_ground_truth_path(Path(self.seed_path))
        if gt_path is not None and gt_path.exists():
            self.ground_truth = json_load(gt_path)

    def _init_db(self) -> None:
        sqlite_dir = Path(self.sqlite_dir)
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(sqlite_dir / f"{self.scenario_id}-{self.episode_id}.db")
        compile_seed(Path(self.seed_path), Path(self.db_path))
        if self.cache is None:
            self.cache = ReplayCache(self.db_path)
        self.policy_manager = AttackerPolicyManager(cache=self.cache)
        self.policy = resolve_attacker_policy()

    def _query_logs(self, sql: str, params: tuple | None = None) -> List[Dict[str, Any]]:
        assert self.db_path is not None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params or ()).fetchall()
            return [dict(r) for r in rows]

    def _fetch_alert(self, alert_id: str) -> Dict[str, Any] | None:
        rows = self._query_logs(
            "SELECT * FROM alerts WHERE scenario_id = ? AND alert_id = ?",
            params=(self.scenario_id, alert_id),
        )
        return rows[0] if rows else None

    def _fetch_email(self, email_id: str) -> Dict[str, Any] | None:
        rows = self._query_logs(
            "SELECT * FROM email_logs WHERE scenario_id = ? AND email_id = ?",
            params=(self.scenario_id, email_id),
        )
        return rows[0] if rows else None

    def _parse_alert_fields(self, message: str) -> Dict[str, str]:
        # Extract key=value pairs from the alert message for structured access.
        if not message:
            return {}
        matches = re.findall(r"([a-zA-Z_]+)=([a-zA-Z0-9_.:@-]+)", message)
        parsed: Dict[str, str] = {}
        for key, value in matches:
            parsed[key] = value
        return parsed

    def _emails_for_step(self, step: int) -> List[str]:
        rows = self._query_logs(
            "SELECT email_id FROM email_logs WHERE scenario_id = ? AND step = ?",
            params=(self.scenario_id, step),
        )
        return [r["email_id"] for r in rows]

    def _alerts_for_step(self, step: int) -> List[str]:
        rows = self._query_logs(
            "SELECT alert_id FROM alerts WHERE scenario_id = ? AND step = ?",
            params=(self.scenario_id, step),
        )
        return [r["alert_id"] for r in rows]

    def _is_readonly_select(self, sql: str) -> bool:
        stripped = sql.strip().lower()
        return stripped.startswith("select")

    def _record_evidence(self, new_emails: List[str], new_alerts: List[str]) -> None:
        for eid in new_emails:
            self.seen_evidence_ids.add(eid)
        for aid in new_alerts:
            self.seen_evidence_ids.add(aid)

    def _record_content_evidence_from_rows(self, rows: List[Dict[str, Any]]) -> None:
        for row in rows:
            if "email_id" in row:
                self.content_evidence_ids.add(str(row["email_id"]))
            if "alert_id" in row:
                self.content_evidence_ids.add(str(row["alert_id"]))
            if "auth_id" in row:
                self.content_evidence_ids.add(str(row["auth_id"]))
            if "flow_id" in row:
                self.content_evidence_ids.add(str(row["flow_id"]))
            if "event_id" in row:
                self.content_evidence_ids.add(str(row["event_id"]))


def json_load(path: Path) -> Dict[str, Any]:
    import json

    with path.open() as f:
        return json.load(f)


def _resolve_ground_truth_path(seed_path: Path) -> Path | None:
    name = seed_path.name
    if name.endswith("_seed.json"):
        return seed_path.with_name(name.replace("_seed.json", "_ground_truth.json"))
    if name.endswith("seed.json"):
        return seed_path.with_name(name.replace("seed.json", "ground_truth.json"))
    return seed_path.with_name("sample_ground_truth.json")
