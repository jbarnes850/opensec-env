#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from server.environment import OpenSecEnvironment
from server.models import AgentAction


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def _infer_from_seed(seed: Dict[str, Any]) -> Dict[str, Any]:
    # Deterministic baseline based on seed contents (no LLM, no heuristics)
    report = {
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
    return report


def run_baseline(seed_path: Path, max_steps: int) -> Dict[str, Any]:
    os.environ.setdefault("OPENSEC_DISABLE_ENV_LOAD", "1")

    seed = _load_json(seed_path)
    env = OpenSecEnvironment(seed_path=str(seed_path))
    env.reset()

    # Minimal investigation: run a safe log query for audit trace
    env.step(AgentAction(action_type="query_logs", params={"sql": "SELECT 1"}))

    # Execute containment actions (required for execution-based scoring)
    env.step(AgentAction(action_type="isolate_host", params={"host_id": seed["patient_zero_host"]}))
    env.step(AgentAction(action_type="block_domain", params={"domain": seed["attacker_domain"]}))
    env.step(AgentAction(action_type="reset_user", params={"user_id": seed["compromised_user"]}))

    report = _infer_from_seed(seed)
    result = env.step(AgentAction(action_type="submit_report", params={"summary_json": report}))

    return {
        "scenario_id": seed["scenario_id"],
        "report": report,
        "reward": result.reward,
        "details": result.info,
        "step_count": env.step_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="data/seeds/sample_seed.json")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--output", default="outputs/baseline_result.json")
    args = parser.parse_args()

    result = run_baseline(Path(args.seed), args.max_steps)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
