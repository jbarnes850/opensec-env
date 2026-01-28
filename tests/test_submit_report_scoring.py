import os

from server.environment import OpenSecEnvironment
from server.models import AgentAction


def test_submit_report_reward():
    os.environ["OPENSEC_DISABLE_ENV_LOAD"] = "1"
    env = OpenSecEnvironment()
    env.reset()

    # Execute containment actions (required for execution-based scoring)
    env.step(AgentAction(action_type="isolate_host", params={"host_id": "h-001"}))
    env.step(AgentAction(action_type="block_domain", params={"domain": "evil-mail.com"}))
    env.step(AgentAction(action_type="reset_user", params={"user_id": "u-001"}))

    report = {
        "patient_zero_host": "h-001",
        "compromised_user": "u-001",
        "attacker_domain": "evil-mail.com",
        "data_target": "t-001",
        "initial_vector": "phish",
        "containment_actions": {
            "isolated_hosts": ["h-001"],
            "blocked_domains": ["evil-mail.com"],
            "reset_users": ["u-001"],
        },
    }
    action = AgentAction(action_type="submit_report", params={"summary_json": report})
    result = env.step(action)

    # Attribution: 5 correct = +5.0
    # Containment: 3 executed = +3.0
    # Efficiency: -0.1 * 4 steps = -0.4
    # Total = 7.6
    assert result.reward == 7.6
