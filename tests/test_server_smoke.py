import os

from fastapi.testclient import TestClient

from server.app import app


def test_reset_step_state():
    os.environ["OPENSEC_DISABLE_ENV_LOAD"] = "1"
    os.environ.pop("OPENAI_API_KEY", None)
    client = TestClient(app)

    reset = client.post("/reset")
    assert reset.status_code == 200
    data = reset.json()
    assert data["observation"]["scenario_id"] == "seed-001"

    step = client.post("/step", json={"action_type": "query_logs", "params": {"sql": "SELECT 1"}})
    assert step.status_code == 200
    step_data = step.json()
    assert step_data["observation"]["last_action_result"]["message"] == "query_logs"

    state = client.get("/state")
    assert state.status_code == 200
    state_data = state.json()
    assert state_data["scenario_id"] == "seed-001"
