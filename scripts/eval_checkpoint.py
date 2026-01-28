#!/usr/bin/env python3
"""Evaluate a trained checkpoint on the OpenSec-Env eval split.

Uses the same evaluation protocol as run_llm_baseline.py but with a local model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from eval_utils import extract_json, injection_evidence_ids, load_env, load_json
from oracle.scoring import containment_to_dict, score_report
from server.environment import OpenSecEnvironment
from server.models import AgentAction
from training.prompts import SYSTEM_PROMPT, build_observation_prompt

ALLOWED_ACTIONS = [
    "query_logs",
    "fetch_email",
    "fetch_alert",
    "isolate_host",
    "block_domain",
    "reset_user",
    "submit_report",
]


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


def _call_sglang(
    url: str,
    model_id: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> str:
    """Call SGLang server via OpenAI-compatible API."""
    response = requests.post(
        f"{url}/v1/chat/completions",
        json={
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _call_local_model(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> str:
    """Call local model directly."""
    if hasattr(tokenizer, "chat_template") and tokenizer.chat_template:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False if "qwen3" in tokenizer.name_or_path.lower() else None
        )
    else:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=temperature > 0,
            temperature=temperature if temperature > 0 else 1.0,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def _invoke_model(
    model: AutoModelForCausalLM | None,
    tokenizer: AutoTokenizer | None,
    sglang_url: str | None,
    sglang_model: str | None,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> tuple[str, Dict[str, Any]]:
    """Invoke model for a single step using full conversation history."""
    if sglang_url:
        if not sglang_model:
            raise ValueError("sglang_model must be provided when using sglang_url")
        text = _call_sglang(sglang_url, sglang_model, messages, max_tokens, temperature)
    elif model is not None and tokenizer is not None:
        text = _call_local_model(model, tokenizer, messages, max_tokens, temperature)
    else:
        raise ValueError("Either sglang_url or model/tokenizer must be provided")

    try:
        return text, extract_json(text)
    except Exception as exc:
        if os.getenv("OPENSEC_DEFENDER_STRICT", "0") == "1":
            raise RuntimeError("defender_invalid_json") from exc
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


def run_episode(
    seed_path: Path,
    model: AutoModelForCausalLM | None,
    tokenizer: AutoTokenizer | None,
    sglang_url: str | None,
    sglang_model: str | None,
    max_steps: int,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Run a single evaluation episode."""
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

    for step_idx in range(max_steps):
        model_text, model_action = _invoke_model(
            model,
            tokenizer,
            sglang_url,
            sglang_model,
            messages,
            temperature,
        )
        messages.append({"role": "assistant", "content": model_text})
        action = _normalize_action(model_action)
        result = env.step(action)
        observation = result.observation.model_dump()
        messages.append({"role": "user", "content": build_observation_prompt(observation)})

        steps.append({
            "step": step_idx,
            "action": action.model_dump(),
            "attacker_action": result.info.get("attacker_action"),
            "injection_violations": result.info.get("injection_violations", []),
        })

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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate trained checkpoint on OpenSec-Env")
    parser.add_argument("--checkpoint", required=True, help="Path to trained checkpoint")
    parser.add_argument("--sglang-url", default=None, help="SGLang server URL (faster than local)")
    parser.add_argument("--sglang-model", default=os.getenv("OPENSEC_SGLANG_MODEL"),
                        help="SGLang model ID (e.g., HF repo or checkpoint path)")
    parser.add_argument("--manifest", default="data/seeds/manifest.json")
    parser.add_argument("--split", default="eval", choices=["train", "eval"])
    parser.add_argument("--tier", default="standard", choices=["trivial", "easy", "standard", "all"])
    parser.add_argument("--limit", type=int, default=0, help="Limit seeds (0 = all)")
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--output", default="outputs/checkpoint_eval.jsonl")
    parser.add_argument("--summary", default="outputs/checkpoint_eval_summary.json")
    args = parser.parse_args()

    load_env()

    # Load model if not using SGLang
    model = None
    tokenizer = None
    if not args.sglang_url:
        print(f"Loading checkpoint: {args.checkpoint}", flush=True)
        tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            args.checkpoint,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        model.eval()
        print("Model loaded", flush=True)
    else:
        if not args.sglang_model:
            args.sglang_model = args.checkpoint
        print(f"Using SGLang server: {args.sglang_url} (model={args.sglang_model})", flush=True)

    # Load seeds
    manifest = load_json(Path(args.manifest))
    seeds = manifest[args.split]
    if args.tier != "all":
        seeds = [entry for entry in seeds if entry.get("tier") == args.tier]
    seeds = [Path(entry["seed_path"]) for entry in seeds]
    if args.limit:
        seeds = seeds[:args.limit]

    print(f"Evaluating on {len(seeds)} seeds ({args.split}/{args.tier})", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rewards: List[float] = []
    containment_executed_count = 0
    report_submitted_count = 0
    correct_containment_count = 0
    false_positive_count = 0
    injection_exposure_count = 0
    injection_violation_count = 0

    with output_path.open("w") as f:
        for i, seed_path in enumerate(seeds):
            print(f"[{i+1}/{len(seeds)}] {seed_path.name}...", end=" ", flush=True)

            result = run_episode(
                seed_path, model, tokenizer,
                args.sglang_url, args.sglang_model,
                args.max_steps, args.temperature
            )

            gt_path = seed_path.with_name(seed_path.name.replace("_seed.json", "_ground_truth.json"))
            ground_truth = load_json(gt_path)

            score = score_report(
                result["report"],
                ground_truth,
                result["step_count"],
                result["injection_violations"],
                executed_containment=result.get("executed_containment"),
            )

            containment_details = score.details.get("containment", {})
            correct_total = 0
            false_total = 0
            for field in ("isolated_hosts", "blocked_domains", "reset_users"):
                field_data = containment_details.get(field, {})
                correct_total += len(field_data.get("correct", []))
                false_total += len(field_data.get("false_positive", []))

            if not result["submitted_report"]:
                score.reward = 0.0
                score.details["failure"] = "no_report_submitted"

            row = {
                "scenario_id": result["scenario_id"],
                "seed_path": result["seed_path"],
                "step_count": result["step_count"],
                "reward": score.reward,
                "details": score.details,
                "submitted_report": result["submitted_report"],
                "executed_containment": result["executed_containment"],
                "containment_correct_total": correct_total,
                "containment_false_positive_total": false_total,
                "diagnostics": result["diagnostics"],
            }
            f.write(json.dumps(row) + "\n")

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

            print(f"reward={score.reward:.2f}, containment={result['diagnostics']['containment_attempted']}", flush=True)

    # Summary statistics
    import statistics
    summary = {
        "checkpoint": args.checkpoint,
        "split": args.split,
        "tier": args.tier,
        "runs": len(rewards),
        "mean_reward": statistics.mean(rewards) if rewards else 0,
        "std_reward": statistics.stdev(rewards) if len(rewards) > 1 else 0,
        "min_reward": min(rewards) if rewards else 0,
        "max_reward": max(rewards) if rewards else 0,
        "containment_executed_rate": containment_executed_count / len(rewards) if rewards else 0,
        "report_submitted_rate": report_submitted_count / len(rewards) if rewards else 0,
        "correct_containment_rate": correct_containment_count / len(rewards) if rewards else 0,
        "false_positive_rate": false_positive_count / len(rewards) if rewards else 0,
        "injection_exposure_rate": injection_exposure_count / len(rewards) if rewards else 0,
        "injection_violation_rate": injection_violation_count / len(rewards) if rewards else 0,
    }

    Path(args.summary).write_text(json.dumps(summary, indent=2))

    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Checkpoint: {args.checkpoint}")
    print(f"Seeds: {len(rewards)} ({args.split}/{args.tier})")
    print(f"Reward: {summary['mean_reward']:.2f} ± {summary['std_reward']:.2f}")
    print(f"Containment Executed: {summary['containment_executed_rate']*100:.1f}%")
    print(f"Report Submitted: {summary['report_submitted_rate']*100:.1f}%")
    print("="*60)
    print(f"\nWrote: {output_path} and {args.summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
