#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Dict, Optional

from server.models import AgentAction

try:
    from client.openenv_client import OpenSecEnv
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "OpenEnv client not available. Install with: pip install '.[openenv]'"
    ) from exc


def _best_effort_value(parsed: Dict[str, str], *keys: str) -> Optional[str]:
    for key in keys:
        value = parsed.get(key)
        if value:
            return value
    return None


def run_green_agent(base_url: str, max_steps: int = 15) -> None:
    with OpenSecEnv(base_url=base_url) as env:
        result = env.reset()
        parsed: Dict[str, str] = {}

        for _ in range(max_steps):
            obs = result.observation

            if obs.new_alerts:
                alert_id = obs.new_alerts[0]
                result = env.step(
                    AgentAction(action_type="fetch_alert", params={"alert_id": alert_id})
                )
                parsed = result.observation.last_action_result.data.get("parsed", {})
                break

            # Fallback: query for any alert id, then fetch
            sql = (
                "SELECT alert_id FROM alerts "
                f"WHERE scenario_id = '{obs.scenario_id}' "
                "ORDER BY step DESC LIMIT 1"
            )
            result = env.step(AgentAction(action_type="query_logs", params={"sql": sql}))
            rows = result.observation.last_action_result.data.get("rows", [])
            if rows:
                alert_id = rows[0].get("alert_id")
                if alert_id:
                    result = env.step(
                        AgentAction(
                            action_type="fetch_alert", params={"alert_id": alert_id}
                        )
                    )
                    parsed = result.observation.last_action_result.data.get("parsed", {})
                    break

        attacker_domain = _best_effort_value(parsed, "dst_domain", "domain")
        patient_zero_host = _best_effort_value(parsed, "src_host", "host")
        compromised_user = _best_effort_value(parsed, "compromised_user", "user")
        data_target = _best_effort_value(parsed, "data_target", "target")

        if patient_zero_host:
            env.step(
                AgentAction(action_type="isolate_host", params={"host_id": patient_zero_host})
            )
        if attacker_domain:
            env.step(
                AgentAction(action_type="block_domain", params={"domain": attacker_domain})
            )
        if compromised_user:
            env.step(
                AgentAction(action_type="reset_user", params={"user_id": compromised_user})
            )

        report = {
            "patient_zero_host": patient_zero_host or "unknown",
            "compromised_user": compromised_user or "unknown",
            "attacker_domain": attacker_domain or "unknown",
            "data_target": data_target or "unknown",
            "initial_vector": "unknown",
            "containment_actions": {
                "isolated_hosts": [patient_zero_host] if patient_zero_host else [],
                "blocked_domains": [attacker_domain] if attacker_domain else [],
                "reset_users": [compromised_user] if compromised_user else [],
            },
        }

        result = env.step(
            AgentAction(action_type="submit_report", params={"summary_json": report})
        )
        print(f"done={result.done} reward={result.reward}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--max-steps", type=int, default=15)
    args = parser.parse_args()

    run_green_agent(args.base_url, args.max_steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
