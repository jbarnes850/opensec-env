from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

LOG_TABLES = {"email_logs", "auth_logs", "netflow", "process_events", "alerts"}


def _parse_kv(template_body: str) -> Dict[str, str]:
    parts = template_body.split()
    kv = {}
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v.strip()
    return kv


def _base_time(seed: Dict) -> datetime:
    created_at = seed.get("metadata", {}).get("created_at")
    if created_at:
        try:
            return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime(2026, 1, 20, tzinfo=timezone.utc)


def _step_time(base: datetime, step: int) -> str:
    return (base + timedelta(minutes=step)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _insert_email(conn: sqlite3.Connection, seed: Dict, email_id: str, step: int) -> None:
    email = next(e for e in seed["seed_artifacts"]["emails"] if e["email_id"] == email_id)
    is_phish = 1 if email.get("injection_id") else 0
    conn.execute(
        """
        INSERT INTO email_logs
        (email_id, scenario_id, step, sender, recipient, subject, body, is_phish, injection_id, trust_tier, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email["email_id"],
            seed["scenario_id"],
            step,
            email["sender"],
            email["recipient"],
            email["subject"],
            email["body"],
            is_phish,
            email.get("injection_id"),
            email.get("trust_tier"),
            email.get("source"),
            _step_time(_base_time(seed), step),
        ),
    )


def _insert_auth(
    conn: sqlite3.Connection,
    seed: Dict,
    step: int,
    template_body: str,
    trust_tier: str | None,
    source: str | None,
) -> None:
    kv = _parse_kv(template_body)
    success = 1 if "success" in template_body.lower() else 0
    conn.execute(
        """
        INSERT INTO auth_logs
        (auth_id, scenario_id, step, user_id, host_id, source_ip, auth_type, success, trust_tier, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"auth-{seed['scenario_id']}-{step}",
            seed["scenario_id"],
            step,
            kv.get("user", seed["compromised_user"]),
            kv.get("host", seed["patient_zero_host"]),
            kv.get("src_ip"),
            kv.get("method", "password"),
            success,
            trust_tier,
            source,
            _step_time(_base_time(seed), step),
        ),
    )


def _insert_netflow(
    conn: sqlite3.Connection,
    seed: Dict,
    step: int,
    template_body: str,
    trust_tier: str | None,
    source: str | None,
) -> None:
    kv = _parse_kv(template_body)
    bytes_sent = int(kv.get("bytes", "0")) if kv.get("bytes", "0").isdigit() else 0
    conn.execute(
        """
        INSERT INTO netflow
        (flow_id, scenario_id, step, src_host, dst_host, dst_domain, dst_port, protocol, bytes_sent, bytes_received, trust_tier, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"flow-{seed['scenario_id']}-{step}",
            seed["scenario_id"],
            step,
            kv.get("src", seed["patient_zero_host"]),
            kv.get("dst"),
            kv.get("dst_domain"),
            int(kv.get("port", "0")) if kv.get("port", "0").isdigit() else None,
            kv.get("proto"),
            bytes_sent,
            0,
            trust_tier,
            source,
            _step_time(_base_time(seed), step),
        ),
    )


def _insert_process(
    conn: sqlite3.Connection,
    seed: Dict,
    step: int,
    template_body: str,
    trust_tier: str | None,
    source: str | None,
) -> None:
    kv = _parse_kv(template_body)
    conn.execute(
        """
        INSERT INTO process_events
        (event_id, scenario_id, step, host_id, user_id, process_name, command_line, parent_process, trust_tier, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"proc-{seed['scenario_id']}-{step}",
            seed["scenario_id"],
            step,
            kv.get("host", seed["patient_zero_host"]),
            kv.get("user", seed["compromised_user"]),
            kv.get("process", "unknown"),
            template_body,
            kv.get("parent"),
            trust_tier,
            source,
            _step_time(_base_time(seed), step),
        ),
    )


def _insert_alert(
    conn: sqlite3.Connection,
    seed: Dict,
    step: int,
    template_body: str,
    injection_id: str | None,
    trust_tier: str | None,
    source: str | None,
) -> None:
    kv = _parse_kv(template_body)
    conn.execute(
        """
        INSERT INTO alerts
        (alert_id, scenario_id, step, alert_type, severity, message, related_log_id, injection_id, trust_tier, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"alert-{seed['scenario_id']}-{step}",
            seed["scenario_id"],
            step,
            kv.get("type", "unknown"),
            kv.get("severity", "medium"),
            template_body,
            None,
            injection_id,
            trust_tier,
            source,
            _step_time(_base_time(seed), step),
        ),
    )


def _insert_prompt_injections(conn: sqlite3.Connection, seed: Dict) -> None:
    for payload in seed.get("prompt_injection_payloads", []):
        evidence_ids = payload.get("evidence_ids")
        evidence_json = json.dumps(evidence_ids) if evidence_ids is not None else None
        target_params = payload.get("target_params")
        target_params_json = json.dumps(target_params) if target_params is not None else None
        conn.execute(
            """
            INSERT OR REPLACE INTO prompt_injections
            (injection_id, scenario_id, surface, payload, expected_violation, target_action, target_params, evidence_ids, injection_type, objective, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["injection_id"],
                seed["scenario_id"],
                payload["surface"],
                payload["payload"],
                payload["expected_violation"],
                payload.get("target_action"),
                target_params_json,
                evidence_json,
                payload.get("injection_type"),
                payload.get("objective"),
                payload.get("source"),
            ),
        )


def _insert_from_template(conn: sqlite3.Connection, seed: Dict, step: int, template: Dict) -> None:
    table = template["table"]
    body = template["template_body"]
    inj_id = template.get("injection_id")
    trust_tier = template.get("trust_tier")
    source = template.get("source")

    if table not in LOG_TABLES:
        raise ValueError(f"Unknown log table: {table}")

    if table == "auth_logs":
        _insert_auth(conn, seed, step, body, trust_tier, source)
    elif table == "netflow":
        _insert_netflow(conn, seed, step, body, trust_tier, source)
    elif table == "process_events":
        _insert_process(conn, seed, step, body, trust_tier, source)
    elif table == "alerts":
        _insert_alert(conn, seed, step, body, inj_id, trust_tier, source)
    elif table == "email_logs":
        _insert_email(conn, seed, template["template_id"], step)


def emit_artifact(
    conn: sqlite3.Connection,
    seed: Dict,
    step: int,
    artifact: Dict,
    log_templates: Dict[str, Dict],
    allow_variant: bool = False,
) -> None:
    if artifact.get("variant_action_type") and not allow_variant:
        return
    if artifact["artifact_type"] == "email":
        _insert_email(conn, seed, artifact["artifact_id"], step)
        return
    if artifact["artifact_type"] in ("log_template", "alert"):
        template = log_templates[artifact["artifact_id"]]
        _insert_from_template(conn, seed, step, template)


def compile_seed(seed_path: Path, db_path: Path) -> None:
    seed = json.loads(seed_path.read_text())
    schema_sql = Path("schemas/sqlite_schema.sql").read_text()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()

        _insert_prompt_injections(conn, seed)

        log_templates = {t["template_id"]: t for t in seed["seed_artifacts"]["log_templates"]}
        attack_graph = seed.get("attack_graph")
        if attack_graph:
            for art in attack_graph.get("initial_artifacts", []):
                step = art.get("step", 0)
                emit_artifact(conn, seed, step, art, log_templates, allow_variant=True)
        else:
            for step_item in seed["attack_plan"]["timeline"]:
                step = step_item["step"]
                for art in step_item["artifacts"]:
                    emit_artifact(conn, seed, step, art, log_templates, allow_variant=False)

        conn.commit()
