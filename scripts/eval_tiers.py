#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List

from eval_utils import load_env, load_json
from oracle.scoring import containment_to_dict
from server.environment import OpenSecEnvironment
from server.models import AgentAction
from sim.attacker_state_machine import STATE_INDEX


def _default_report() -> Dict[str, Any]:
    return {
        "patient_zero_host": "unknown",
        "compromised_user": "unknown",
        "attacker_domain": "unknown",
        "data_target": "unknown",
        "initial_vector": "phish",
        "containment_actions": {"isolated_hosts": [], "blocked_domains": [], "reset_users": []},
    }


def _oracle_report(seed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_zero_host": seed["patient_zero_host"],
        "compromised_user": seed["compromised_user"],
        "attacker_domain": seed["attacker_domain"],
        "data_target": seed["data_target"],
        "initial_vector": seed["attack_plan"]["initial_vector"],
        "containment_actions": {
            "isolated_hosts": [seed["patient_zero_host"]],
            "blocked_domains": [seed["attacker_domain"]],
            "reset_users": [seed["compromised_user"]],
        },
    }


def _attack_graph_progress(seed: Dict[str, Any], attacker_state: str) -> int | None:
    graph = seed.get("attack_graph") or {}
    objectives = graph.get("objectives") or []
    if objectives:
        index_map = {state: idx for idx, state in enumerate(objectives)}
        if attacker_state in index_map:
            return index_map[attacker_state]
    return STATE_INDEX.get(attacker_state)


@contextmanager
def _temp_env(overrides: Dict[str, str | None]):
    prior: Dict[str, str | None] = {}
    for key, value in overrides.items():
        prior[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _attacker_episode_metrics(
    trace: List[Dict[str, Any]],
    attacker_state: str,
    attacker_context: Dict[str, Any],
) -> Dict[str, Any]:
    exfil_attempts = 0
    time_to_exfil = None
    lateral_spread_hosts = set()
    persistence = False
    stall_reason = None

    for entry in trace:
        action = entry.get("attacker_action") or {}
        action_type = action.get("action_type")
        params = action.get("params") or {}

        if action_type:
            if action_type.startswith("exfiltrate"):
                exfil_attempts += 1
                if time_to_exfil is None:
                    time_to_exfil = entry.get("step_index")
            if action_type in ("lateral_move", "lateral_move_alt", "lateral_spread", "pivot"):
                dst = params.get("dst") or params.get("host") or params.get("target_host")
                if dst:
                    lateral_spread_hosts.add(dst)
            if action_type in ("establish_persistence", "persistence"):
                persistence = True

        if entry.get("attacker_stalled"):
            stall_reason = entry.get("attacker_reason")

    persistence_established = persistence or attacker_context.get("has_persistence", False)

    reached_exfil = attacker_state == "exfil_attempt" or exfil_attempts > 0

    return {
        "attacker_reached_exfil": reached_exfil,
        "exfil_attempt_count": exfil_attempts,
        "persistence_established": persistence_established,
        "lateral_spread_count": len(lateral_spread_hosts),
        "time_to_exfil": time_to_exfil,
        "stall_reason": stall_reason,
    }


def _run_episode(seed_path: Path, defender: str, max_steps: int) -> Dict[str, Any]:
    seed = load_json(seed_path)
    env = OpenSecEnvironment(seed_path=str(seed_path))
    reset = env.reset()
    episode_max_steps = min(max_steps, env.max_steps)

    if defender == "oracle":
        report = _oracle_report(seed)
        actions = [
            AgentAction(action_type="query_logs", params={"sql": "SELECT 1"}),
            AgentAction(action_type="isolate_host", params={"host_id": seed["patient_zero_host"]}),
            AgentAction(action_type="block_domain", params={"domain": seed["attacker_domain"]}),
            AgentAction(action_type="reset_user", params={"user_id": seed["compromised_user"]}),
        ]
    else:
        report = _default_report()
        actions = [AgentAction(action_type="query_logs", params={"sql": "SELECT 1"})]

    step_results: List[Dict[str, Any]] = []
    remaining = max(0, episode_max_steps - 1)
    for step_idx in range(remaining):
        action = actions[step_idx] if step_idx < len(actions) else actions[0]
        result = env.step(action)
        step_results.append(
            {
                "step_index": step_idx + 1,
                "action": action.model_dump(),
                "attacker_action": result.info.get("attacker_action"),
                "attacker_state": result.observation.attacker_state,
                "attacker_stalled": result.info.get("attacker_stalled"),
                "attacker_reason": result.info.get("attacker_reason"),
                "injection_violations": result.info.get("injection_violations", []),
            }
        )

    final_action = AgentAction(action_type="submit_report", params={"summary_json": report})
    final = env.step(final_action)
    step_results.append(
        {
            "step_index": env.step_count,
            "action": final_action.model_dump(),
            "attacker_action": final.info.get("attacker_action"),
            "attacker_state": final.observation.attacker_state,
            "attacker_stalled": final.info.get("attacker_stalled"),
            "attacker_reason": final.info.get("attacker_reason"),
            "injection_violations": final.info.get("injection_violations", []),
        }
    )

    executed_containment = containment_to_dict(env.containment)
    containment_attempted = bool(
        env.containment.isolated_hosts
        or env.containment.blocked_domains
        or env.containment.reset_users
    )

    attacker_state = final.observation.attacker_state
    attacker_progress = _attack_graph_progress(seed, attacker_state)
    attacker_context = {
        "has_persistence": env.attacker_context.has_persistence,
        "has_stage": env.attacker_context.has_stage,
        "has_admin": env.attacker_context.has_admin,
        "has_creds": env.attacker_context.has_creds,
    }
    attacker_metrics = _attacker_episode_metrics(step_results, attacker_state, attacker_context)

    return {
        "scenario_id": env.scenario_id,
        "seed_path": str(seed_path),
        "step_count": env.step_count,
        "reward": final.reward,
        "executed_containment": executed_containment,
        "containment_attempted": containment_attempted,
        "injection_violations": list(env.injection_violations),
        "attacker_state": attacker_state,
        "attacker_progress": attacker_progress,
        **attacker_metrics,
        "trace": step_results,
    }


def _summarize(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    total = len(rows)
    if total == 0:
        return {
            "episodes": 0,
            "mean_reward": 0.0,
            "containment_rate": 0.0,
            "injection_rate": 0.0,
            "attacker_reached_exfil_rate": 0.0,
            "exfil_attempt_mean": 0.0,
            "persistence_established_rate": 0.0,
            "lateral_spread_mean": 0.0,
            "time_to_exfil_mean": None,
            "mean_steps": 0.0,
        }

    mean_reward = sum(r["reward"] for r in rows) / total
    containment_rate = sum(1 for r in rows if r["containment_attempted"]) / total
    injection_rate = sum(1 for r in rows if r["injection_violations"]) / total
    exfil_rate = sum(1 for r in rows if r["attacker_reached_exfil"]) / total
    exfil_attempt_mean = sum(r["exfil_attempt_count"] for r in rows) / total
    persistence_rate = sum(1 for r in rows if r["persistence_established"]) / total
    lateral_spread_mean = sum(r["lateral_spread_count"] for r in rows) / total
    exfil_times = [r["time_to_exfil"] for r in rows if r["time_to_exfil"] is not None]
    time_to_exfil_mean = sum(exfil_times) / len(exfil_times) if exfil_times else None
    mean_steps = sum(r["step_count"] for r in rows) / total

    return {
        "episodes": total,
        "mean_reward": round(mean_reward, 4),
        "containment_rate": round(containment_rate, 4),
        "injection_rate": round(injection_rate, 4),
        "attacker_reached_exfil_rate": round(exfil_rate, 4),
        "exfil_attempt_mean": round(exfil_attempt_mean, 4),
        "persistence_established_rate": round(persistence_rate, 4),
        "lateral_spread_mean": round(lateral_spread_mean, 4),
        "time_to_exfil_mean": round(time_to_exfil_mean, 4) if time_to_exfil_mean is not None else None,
        "mean_steps": round(mean_steps, 4),
    }


def _preflight_sglang(base_url: str) -> None:
    url = base_url.rstrip("/") + "/models"
    try:
        with urlrequest.urlopen(url, timeout=5) as response:
            if response.status >= 400:
                raise RuntimeError(f"SGLang returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or "data" not in payload:
                raise RuntimeError("SGLang response missing models payload")
    except Exception as exc:
        raise SystemExit(
            "Strict attacker is enabled but the SGLang backend is not reachable. "
            f"Check SGLANG_BASE_URL ({base_url}) and ensure the server is running. "
            f"Details: {exc}"
        ) from exc


def _preflight_openai(api_key: str) -> None:
    url = "https://api.openai.com/v1/models"
    request = urlrequest.Request(url)
    request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlrequest.urlopen(request, timeout=5) as response:
            if response.status >= 400:
                raise RuntimeError(f"OpenAI returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or "data" not in payload:
                raise RuntimeError("OpenAI response missing models payload")
    except urlerror.URLError as exc:
        raise SystemExit(
            "Strict attacker is enabled but the OpenAI backend is not reachable. "
            f"Details: {exc}"
        ) from exc
    except Exception as exc:
        raise SystemExit(
            "Strict attacker is enabled but the OpenAI backend check failed. "
            f"Details: {exc}"
        ) from exc


def _preflight_live_backend() -> None:
    if os.getenv("OPENSEC_ATTACKER_SGLANG") == "1":
        base_url = os.getenv("SGLANG_BASE_URL", "http://localhost:30000/v1")
        _preflight_sglang(base_url)
    elif os.getenv("OPENAI_API_KEY"):
        _preflight_openai(os.getenv("OPENAI_API_KEY", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/seeds/manifest.json")
    parser.add_argument("--split", default="eval", choices=["train", "eval"])
    parser.add_argument("--tier", default=None, choices=["trivial", "easy", "standard"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--defender", default="noop", choices=["noop", "oracle"])
    parser.add_argument("--output-dir", default="outputs/tier_eval")
    parser.add_argument("--replay-mode", default="record", choices=["off", "record", "replay"])
    parser.add_argument("--replay-cache", default="")
    parser.add_argument("--tiers", default="T0,T1,T2", help="Comma-separated tiers to run")
    parser.add_argument("--strict-attacker", default="1", choices=["0", "1"])
    args = parser.parse_args()

    load_env()

    if args.strict_attacker == "1":
        has_sglang = os.getenv("OPENSEC_ATTACKER_SGLANG") == "1"
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        if not (has_sglang or has_openai):
            raise SystemExit(
                "Strict attacker is enabled but no live LLM backend is configured. "
                "Set OPENSEC_ATTACKER_SGLANG=1 or OPENAI_API_KEY."
            )
        _preflight_live_backend()

    manifest = load_json(Path(args.manifest))
    seeds = manifest[args.split]
    if args.tier:
        seeds = [entry for entry in seeds if entry.get("tier") == args.tier]
    if args.limit:
        seeds = seeds[: args.limit]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tiers = [
        {
            "name": "T0",
            "env": {
                "OPENSEC_ATTACKER_SANDBOX": "0",
                "OPENSEC_ATTACKER_SGLANG": None,
                "OPENAI_API_KEY": None,
            },
        },
        {
            "name": "T1",
            "env": {
                "OPENSEC_ATTACKER_SANDBOX": "0",
            },
        },
        {
            "name": "T2",
            "env": {
                "OPENSEC_ATTACKER_SANDBOX": "1",
            },
        },
    ]

    summaries: Dict[str, Any] = {}
    gate_failures: List[str] = []
    wanted = {t.strip().upper() for t in args.tiers.split(",") if t.strip()}
    for tier in tiers:
        if tier["name"] not in wanted:
            continue
        tier_env = dict(tier["env"])
        tier_env["OPENSEC_REPLAY_MODE"] = args.replay_mode
        if args.replay_cache:
            tier_env["OPENSEC_REPLAY_CACHE_PATH"] = args.replay_cache
        if tier["name"] in {"T1", "T2"}:
            tier_env["OPENSEC_ATTACKER_STRICT"] = args.strict_attacker
        else:
            tier_env["OPENSEC_ATTACKER_STRICT"] = "0"

        rows: List[Dict[str, Any]] = []
        with _temp_env(tier_env):
            for entry in seeds:
                seed_path = Path(entry["seed_path"])
                rows.append(_run_episode(seed_path, args.defender, args.max_steps))

        out_path = output_dir / f"tier_{tier['name'].lower()}.jsonl"
        with out_path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

        summaries[tier["name"]] = _summarize(rows)
        if tier["name"] in {"T1", "T2"} and summaries[tier["name"]]["episodes"] > 0:
            if summaries[tier["name"]]["attacker_reached_exfil_rate"] == 0.0:
                gate_failures.append(
                    f"{tier['name']}: attacker_reached_exfil_rate == 0"
                )

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2))
    print(json.dumps(summaries, indent=2))
    if gate_failures:
        print("Tier eval gate failed: " + "; ".join(gate_failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
