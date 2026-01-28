#!/usr/bin/env python3
import json
import sys
from pathlib import Path

LOG_TABLES = {"email_logs", "auth_logs", "netflow", "process_events", "alerts"}


def _err(msg):
    print(f"ERROR: {msg}")


def _load_json(path):
    with path.open() as f:
        return json.load(f)


def validate_seed(seed):
    errors = 0

    users = {u["user_id"] for u in seed["entities"]["users"]}
    hosts = {h["host_id"] for h in seed["entities"]["hosts"]}
    domains = {d["domain"] for d in seed["entities"]["domains"]}
    targets = {t["target_id"] for t in seed["entities"]["data_targets"]}

    emails = {e["email_id"] for e in seed["seed_artifacts"]["emails"]}
    log_templates = {t["template_id"]: t for t in seed["seed_artifacts"]["log_templates"]}

    # Top-level references
    if seed["patient_zero_host"] not in hosts:
        _err("patient_zero_host not in entities.hosts")
        errors += 1
    if seed["compromised_user"] not in users:
        _err("compromised_user not in entities.users")
        errors += 1
    if seed["attacker_domain"] not in domains:
        _err("attacker_domain not in entities.domains")
        errors += 1
    if seed["data_target"] not in targets:
        _err("data_target not in entities.data_targets")
        errors += 1

    # attack_plan references
    ap = seed["attack_plan"]
    if ap["phishing_email_id"] not in emails:
        _err("attack_plan.phishing_email_id not in seed_artifacts.emails")
        errors += 1
    if ap["credentials_used"]["user_id"] not in users:
        _err("attack_plan.credentials_used.user_id not in entities.users")
        errors += 1
    for hop in ap["lateral_path"]:
        if hop["src_host"] not in hosts:
            _err("attack_plan.lateral_path.src_host not in entities.hosts")
            errors += 1
        if hop["dst_host"] not in hosts:
            _err("attack_plan.lateral_path.dst_host not in entities.hosts")
            errors += 1
    if ap["data_access"]["target_id"] not in targets:
        _err("attack_plan.data_access.target_id not in entities.data_targets")
        errors += 1
    if ap["exfiltration"]["destination_domain"] not in domains:
        _err("attack_plan.exfiltration.destination_domain not in entities.domains")
        errors += 1

    # timeline artifacts (attack_plan timeline + attack_graph initial_artifacts)
    artifact_events = list(ap.get("timeline", []))
    attack_graph = seed.get("attack_graph")
    if attack_graph:
        for art in attack_graph.get("initial_artifacts", []):
            artifact_events.append({"step": art.get("step", 0), "artifacts": [art]})

    for item in artifact_events:
        for art in item["artifacts"]:
            art_type = art["artifact_type"]
            art_id = art["artifact_id"]
            if art_type == "email":
                if art_id not in emails:
                    _err("timeline artifact email not in seed_artifacts.emails")
                    errors += 1
            elif art_type == "log_template":
                if art_id not in log_templates:
                    _err("timeline artifact log_template not in seed_artifacts.log_templates")
                    errors += 1
            elif art_type == "alert":
                if art_id not in log_templates:
                    _err("timeline artifact alert not in seed_artifacts.log_templates")
                    errors += 1
                else:
                    table = log_templates[art_id]["table"]
                    if table != "alerts":
                        _err("timeline artifact alert must reference log_template with table=alerts")
                        errors += 1
            variant_action = art.get("variant_action_type")
            if variant_action and variant_action not in {
                "lateral_move",
                "lateral_move_alt",
                "exfiltrate",
                "exfiltrate_alt",
            }:
                _err("timeline artifact variant_action_type not allowed")
                errors += 1

    # prompt injection mapping
    injections = seed["prompt_injection_payloads"]
    injection_ids = {p["injection_id"] for p in injections}
    if len(injection_ids) != len(injections):
        _err("prompt_injection_payloads injection_id must be unique")
        errors += 1

    template_by_injection = {
        t.get("injection_id"): t for t in seed["seed_artifacts"]["log_templates"] if t.get("injection_id")
    }
    timeline_steps = {}
    for item in artifact_events:
        for art in item["artifacts"]:
            if art["artifact_type"] in ("log_template", "alert"):
                timeline_steps.setdefault(art["artifact_id"], item["step"])

    for p in injections:
        inj_id = p["injection_id"]
        if p["surface"] == "email":
            if not any(e.get("injection_id") == inj_id for e in seed["seed_artifacts"]["emails"]):
                _err("email injection_id not referenced by any seed_artifacts.emails")
                errors += 1
        elif p["surface"] == "alert":
            if not any(
                t.get("injection_id") == inj_id and t.get("table") == "alerts"
                for t in seed["seed_artifacts"]["log_templates"]
            ):
                _err("alert injection_id not referenced by any alerts log_template")
                errors += 1
            else:
                template = template_by_injection.get(inj_id)
                if template:
                    step = timeline_steps.get(template.get("template_id"))
                    if step is not None:
                        expected = f"alert-{seed['scenario_id']}-{step}"
                        evidence_ids = set(p.get("evidence_ids", []))
                        if expected not in evidence_ids:
                            _err("alert injection evidence_ids missing expected alert id")
                            errors += 1
        elif p["surface"] == "log":
            template = template_by_injection.get(inj_id)
            if not template:
                _err("log injection_id not referenced by any log_template")
                errors += 1
            else:
                table = template.get("table")
                if table not in {"auth_logs", "netflow", "process_events"}:
                    _err("log injection_id must reference auth_logs/netflow/process_events template")
                    errors += 1
                step = timeline_steps.get(template.get("template_id"))
                if step is None:
                    _err("log injection template_id not present in timeline")
                    errors += 1
                else:
                    expected = None
                    if table == "auth_logs":
                        expected = f"auth-{seed['scenario_id']}-{step}"
                    elif table == "netflow":
                        expected = f"flow-{seed['scenario_id']}-{step}"
                    elif table == "process_events":
                        expected = f"proc-{seed['scenario_id']}-{step}"
                    evidence_ids = set(p.get("evidence_ids", []))
                    if expected and expected not in evidence_ids:
                        _err("log injection evidence_ids missing expected row id")
                        errors += 1

    # basic log_template table validation
    for t in seed["seed_artifacts"]["log_templates"]:
        if t["table"] not in LOG_TABLES:
            _err(f"log_template table not recognized: {t['table']}")
            errors += 1

    return errors


def main(argv):
    if len(argv) < 2:
        candidates = [p for p in Path("data/seeds").glob("*.json") if "ground_truth" not in p.name]
    else:
        candidates = [Path(p) for p in argv[1:]]

    total_errors = 0
    for path in candidates:
        seed = _load_json(path)
        errs = validate_seed(seed)
        if errs == 0:
            print(f"OK: {path}")
        total_errors += errs

    if total_errors > 0:
        print(f"Validation failed with {total_errors} error(s)")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
