import json
import pytest
from training.rollout import _parse_action, ALLOWED_ACTIONS


def test_parse_action_valid_json():
    text = '{"action_type": "fetch_alert", "params": {"alert_id": "alert-001"}}'
    action = _parse_action(text)
    assert action is not None
    assert action["action_type"] == "fetch_alert"
    assert action["params"]["alert_id"] == "alert-001"


def test_parse_action_with_surrounding_text():
    text = 'Here is the action: {"action_type": "isolate_host", "params": {"host_id": "h-001"}} done'
    action = _parse_action(text)
    assert action is not None
    assert action["action_type"] == "isolate_host"


def test_parse_action_invalid_action_type():
    text = '{"action_type": "invalid_action", "params": {}}'
    action = _parse_action(text)
    assert action is None


def test_parse_action_no_json():
    text = "This is just plain text without JSON"
    action = _parse_action(text)
    assert action is None


def test_parse_action_malformed_json():
    text = '{"action_type": "fetch_alert", "params": '
    action = _parse_action(text)
    assert action is None


def test_parse_action_query_logs_adds_default_sql():
    text = '{"action_type": "query_logs", "params": {}}'
    action = _parse_action(text)
    assert action is not None
    assert action["params"]["sql"] == "SELECT 1"


def test_parse_action_query_logs_preserves_sql():
    text = '{"action_type": "query_logs", "params": {"sql": "SELECT * FROM alerts"}}'
    action = _parse_action(text)
    assert action is not None
    assert action["params"]["sql"] == "SELECT * FROM alerts"


def test_parse_action_submit_report():
    text = '{"action_type": "submit_report", "params": {"summary_json": {"patient_zero_host": "h-001"}}}'
    action = _parse_action(text)
    assert action is not None
    assert action["action_type"] == "submit_report"
    assert action["params"]["summary_json"]["patient_zero_host"] == "h-001"


def test_all_allowed_actions_valid():
    for action_type in ALLOWED_ACTIONS:
        text = json.dumps({"action_type": action_type, "params": {}})
        action = _parse_action(text)
        assert action is not None, f"Failed for action_type: {action_type}"
        assert action["action_type"] == action_type
