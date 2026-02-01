#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

from openai import OpenAI, BadRequestError

from eval_utils import extract_json, injection_evidence_ids, load_env, load_json
from oracle.scoring import containment_to_dict, score_report
from server.environment import OpenSecEnvironment
from server.models import AgentAction
from prompts import SYSTEM_PROMPT, build_observation_prompt

ALLOWED_ACTIONS = [
    "query_logs",
    "fetch_email",
    "fetch_alert",
    "isolate_host",
    "block_domain",
    "reset_user",
    "submit_report",
]


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


def _normalize_action(data: Dict[str, Any]) -> AgentAction:
    action_type = data.get("action_type") if isinstance(data, dict) else None
    if action_type not in ALLOWED_ACTIONS:
        action_type = "query_logs"
    params = data.get("params") if isinstance(data, dict) and isinstance(data.get("params"), dict) else {}

    if action_type == "query_logs" and "sql" not in params:
        params["sql"] = "SELECT 1"
    if action_type == "fetch_email" and "email_id" not in params:
        params["email_id"] = ""
    if action_type == "fetch_alert" and "alert_id" not in params:
        params["alert_id"] = ""

    return AgentAction(action_type=action_type, params=params)


def _call_openai(model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    request = {
        "model": model,
        "input": messages,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        response = client.responses.create(**request)
    except Exception as exc:
        if isinstance(exc, BadRequestError) and "temperature" in str(exc).lower():
            request.pop("temperature", None)
            response = client.responses.create(**request)
        else:
            raise
    text = getattr(response, "output_text", None)
    if text is None:
        text = str(response)
    return text


def _call_openrouter(model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _invoke_model(model_cfg: Dict[str, Any], messages: List[Dict[str, str]]) -> tuple[str, Dict[str, Any]]:

    provider = model_cfg["provider"]
    temperature = float(model_cfg.get("temperature", 0.2))
    max_tokens = int(model_cfg.get("max_tokens", 600))

    if provider == "openai":
        text = _call_openai(model_cfg["name"], messages, temperature, max_tokens)
    elif provider == "openrouter":
        text = _call_openrouter(model_cfg["name"], messages, temperature, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        return text, extract_json(text)
    except Exception:
        return text, {"action_type": "query_logs", "params": {"sql": "SELECT 1"}}


def _default_report() -> Dict[str, Any]:
    return {
        "patient_zero_host": "unknown",
        "compromised_user": "unknown",
        "attacker_domain": "unknown",
        "data_target": "unknown",
        "initial_vector": "phish",
        "containment_actions": {"isolated_hosts": [], "blocked_domains": [], "reset_users": []},
    }


def run_episode(seed_path: Path, model_cfg: Dict[str, Any], max_steps: int) -> Dict[str, Any]:
    env = OpenSecEnvironment(seed_path=str(seed_path))
    reset_result = env.reset()
    observation = reset_result.observation.model_dump()

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(max_steps=max_steps)}
    ]
    messages.append({"role": "user", "content": build_observation_prompt(observation)})

    steps: List[Dict[str, Any]] = []
    report: Dict[str, Any] | None = None
    submitted_report = False

    for _ in range(max_steps):
        model_text, model_action = _invoke_model(model_cfg, messages)
        action = _normalize_action(model_action)
        result = env.step(action)
        observation = result.observation.model_dump()
        messages.append({"role": "assistant", "content": model_text})
        messages.append({"role": "user", "content": build_observation_prompt(observation)})

        steps.append(
            {
                "action": action.model_dump(),
                "attacker_action": result.info.get("attacker_action"),
                "injection_violations": result.info.get("injection_violations", []),
            }
        )

        if action.action_type == "submit_report":
            report = action.params.get("summary_json")
            submitted_report = True
            break

    if report is None:
        report = _default_report()
        result = env.step(AgentAction(action_type="submit_report", params={"summary_json": report}))

    injection_evidence = injection_evidence_ids(env.scenario)
    injection_encountered = injection_evidence.intersection(env.content_evidence_ids)
    containment_attempted = bool(
        env.containment.isolated_hosts
        or env.containment.blocked_domains
        or env.containment.reset_users
    )
    attacker_model = os.getenv("OPENAI_ATTACKER_MODEL")
    attacker_temp = os.getenv("OPENAI_ATTACKER_TEMPERATURE")
    replay_cache = os.getenv("OPENSEC_REPLAY_CACHE_PATH")

    executed_containment = containment_to_dict(env.containment)

    return {
        "scenario_id": env.scenario_id,
        "seed_path": str(seed_path),
        "step_count": env.step_count,
        "report": report,
        "executed_containment": executed_containment,
        "submitted_report": submitted_report,
        "steps": steps,
        "injection_violations": result.info.get("injection_violations", []),
        "diagnostics": {
            "evidence_seen_count": len(env.seen_evidence_ids),
            "evidence_content_count": len(env.content_evidence_ids),
            "injection_evidence_total": len(injection_evidence),
            "injection_evidence_seen": len(injection_encountered),
            "containment_attempted": containment_attempted,
            "report_submitted": submitted_report,
        },
        "attacker_config": {
            "model": attacker_model,
            "temperature": attacker_temp,
            "replay_cache_path": replay_cache,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baselines.yaml")
    parser.add_argument("--manifest", default="data/seeds/manifest.json")
    parser.add_argument("--split", default="eval", choices=["train", "eval"])
    parser.add_argument("--tier", default=None, choices=["trivial", "easy", "standard"])
    parser.add_argument("--models", default="", help="Comma-separated model names to run (subset)")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--output", default="outputs/llm_baselines.jsonl")
    parser.add_argument("--summary", default="outputs/llm_baselines_summary.json")
    args = parser.parse_args()

    load_env()

    config = _load_yaml(Path(args.config))
    model_list = config.get("models", [])
    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        model_list = [m for m in model_list if m.get("name") in wanted]

    manifest = load_json(Path(args.manifest))
    seeds = manifest[args.split]
    if args.tier:
        seeds = [entry for entry in seeds if entry.get("tier") == args.tier]
    seeds = [Path(entry["seed_path"]) for entry in seeds]
    if args.limit:
        seeds = seeds[: args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {}

    with output_path.open("w") as f:
        for model_cfg in model_list:
            rewards: List[float] = []
            containment_executed_count = 0
            report_submitted_count = 0
            correct_containment_count = 0
            false_positive_count = 0
            injection_exposure_count = 0
            injection_violation_count = 0
            for idx, seed_path in enumerate(seeds, start=1):
                result = run_episode(seed_path, model_cfg, args.max_steps)
                gt_path = seed_path.with_name(seed_path.name.replace("_seed.json", "_ground_truth.json"))
                ground_truth = load_json(gt_path)
                score = score_report(
                    result["report"],
                    ground_truth,
                    result["step_count"],
                    result["injection_violations"],
                    executed_containment=result.get("executed_containment"),
                )
                if not result["submitted_report"]:
                    score.reward = 0.0
                    score.details["failure"] = "no_report_submitted"

                containment_details = score.details.get("containment", {})
                correct_total = 0
                false_total = 0
                for field in ("isolated_hosts", "blocked_domains", "reset_users"):
                    field_data = containment_details.get(field, {})
                    correct_total += len(field_data.get("correct", []))
                    false_total += len(field_data.get("false_positive", []))

                row = {
                    "model": model_cfg["name"],
                    "provider": model_cfg["provider"],
                    "scenario_id": result["scenario_id"],
                    "seed_path": result["seed_path"],
                    "step_count": result["step_count"],
                    "reward": score.reward,
                    "details": score.details,
                    "submitted_report": result["submitted_report"],
                    "steps": result["steps"],
                    "executed_containment": result["executed_containment"],
                    "diagnostics": result["diagnostics"],
                    "containment_correct_total": correct_total,
                    "containment_false_positive_total": false_total,
                }
                f.write(json.dumps(row) + "\n")
                f.flush()
                print(
                    f"[{idx}/{len(seeds)}] {model_cfg['name']} {seed_path.name} "
                    f"reward={score.reward:.2f} containment={result['diagnostics']['containment_attempted']}",
                    flush=True,
                )
                rewards.append(score.reward)

                if result["diagnostics"]["containment_attempted"]:
                    containment_executed_count += 1
                if result["submitted_report"]:
                    report_submitted_count += 1
                if correct_total > 0:
                    correct_containment_count += 1
                if false_total > 0:
                    false_positive_count += 1
                if result["diagnostics"]["injection_evidence_seen"] > 0:
                    injection_exposure_count += 1
                if score.details.get("injection", {}).get("violations"):
                    injection_violation_count += 1

            if rewards:
                summary[model_cfg["name"]] = {
                    "provider": model_cfg["provider"],
                    "runs": len(rewards),
                    "mean_reward": sum(rewards) / len(rewards),
                    "min_reward": min(rewards),
                    "max_reward": max(rewards),
                    "containment_executed_rate": containment_executed_count / len(rewards),
                    "report_submitted_rate": report_submitted_count / len(rewards),
                    "correct_containment_rate": correct_containment_count / len(rewards),
                    "false_positive_rate": false_positive_count / len(rewards),
                    "injection_exposure_rate": injection_exposure_count / len(rewards),
                    "injection_violation_rate": injection_violation_count / len(rewards),
                }

    Path(args.summary).write_text(json.dumps(summary, indent=2))
    print(f"OK: wrote {output_path} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
