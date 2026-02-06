import os

from fastapi.testclient import TestClient

from server.app import app


def test_reset_and_state():
    """Verify /reset returns a valid observation and /state returns episode info."""
    os.environ["OPENSEC_DISABLE_ENV_LOAD"] = "1"
    os.environ.pop("OPENAI_API_KEY", None)
    client = TestClient(app)

    reset = client.post("/reset")
    assert reset.status_code == 200
    data = reset.json()
    assert data["observation"]["scenario_id"] == "seed-001"

    state = client.get("/state")
    assert state.status_code == 200
    state_data = state.json()
    assert "step_count" in state_data
    assert state_data["step_count"] == 0
