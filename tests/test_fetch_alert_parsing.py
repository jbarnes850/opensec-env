import json
from pathlib import Path

from server.environment import OpenSecEnvironment
from server.models import AgentAction


def _load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def test_fetch_alert_parses_fields():
    seed_path = Path("data/seeds/eval/trivial-001_seed.json")
    seed = _load_json(seed_path)

    env = OpenSecEnvironment(seed_path=str(seed_path))
    reset = env.reset()
    assert reset.observation.new_alerts, "expected initial alert"

    alert_id = reset.observation.new_alerts[0]
    result = env.step(AgentAction(action_type="fetch_alert", params={"alert_id": alert_id}))
    data = result.observation.last_action_result.data
    parsed = data.get("parsed", {})

    assert parsed.get("dst_domain") == seed["attacker_domain"]
    assert parsed.get("src_host") == seed["patient_zero_host"]
    assert parsed.get("compromised_user") == seed["compromised_user"]
    assert parsed.get("data_target") == seed["data_target"]
