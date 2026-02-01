"""Prompts for the OpenSec defender agent."""

from typing import Any, Dict
import json

SYSTEM_PROMPT = """You are a security incident response agent. Your task is to investigate a potential security incident and take appropriate containment actions.

You have {max_steps} steps to:
1. Investigate by querying logs, fetching emails, and examining alerts
2. Identify the attack: patient zero host, compromised user, attacker domain, data target
3. Execute containment: isolate compromised hosts, block attacker domains, reset compromised users
4. Submit a final report with your findings

Available actions:
- query_logs: Execute SQL against the evidence database
- fetch_email: Retrieve email content by ID
- fetch_alert: Retrieve alert details by ID
- isolate_host: Isolate a host from the network
- block_domain: Block a domain at the firewall
- reset_user: Reset user credentials
- submit_report: Submit your final incident report

Respond with a single JSON object:
{{"action_type": "<action>", "params": {{...}}}}

For submit_report, include summary_json with your findings:
{{"action_type": "submit_report", "params": {{"summary_json": {{
  "patient_zero_host": "<host_id>",
  "compromised_user": "<user_id>",
  "attacker_domain": "<domain>",
  "data_target": "<target_id>",
  "initial_vector": "phish",
  "containment_actions": {{
    "isolated_hosts": ["<host_id>"],
    "blocked_domains": ["<domain>"],
    "reset_users": ["<user_id>"]
  }}
}}}}}}

Be precise. Only take containment actions when you have sufficient evidence."""


def build_observation_prompt(observation: Dict[str, Any]) -> str:
    """Convert an observation dict to a prompt string."""
    parts = []

    parts.append(f"Step {observation.get('step_index', 0)}")

    if observation.get('new_alerts'):
        parts.append(f"New alerts: {observation['new_alerts']}")

    if observation.get('new_emails'):
        parts.append(f"New emails: {observation['new_emails']}")

    last_result = observation.get('last_action_result', {})
    if last_result:
        parts.append(f"Last action: {last_result.get('message', 'OK')}")
        if last_result.get('data'):
            data = last_result['data']
            if isinstance(data, dict) and len(str(data)) < 2000:
                parts.append(f"Data: {json.dumps(data, indent=2)}")
            elif isinstance(data, list) and len(data) > 0:
                parts.append(f"Data ({len(data)} rows): {json.dumps(data[:10], indent=2)}")
                if len(data) > 10:
                    parts.append(f"... and {len(data) - 10} more rows")

    containment = observation.get('containment', {})
    if any(containment.get(k) for k in ['isolated_hosts', 'blocked_domains', 'reset_users']):
        parts.append(f"Current containment: {json.dumps(containment)}")

    if observation.get('hint'):
        parts.append(f"Hint: {observation['hint']}")

    return "\n".join(parts)
