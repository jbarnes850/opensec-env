import json
from pathlib import Path

from oracle.scoring import containment_to_dict, score_report


def test_score_report_perfect():
    ground_truth = json.loads(Path("data/seeds/sample_ground_truth.json").read_text())
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
    score = score_report(report, ground_truth, step_count=5, injection_violations=[])
    assert score.reward == 7.5


def test_score_report_with_violation():
    ground_truth = json.loads(Path("data/seeds/sample_ground_truth.json").read_text())
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
    score = score_report(report, ground_truth, step_count=5, injection_violations=["inj-001"])
    assert score.reward == 5.5


def test_score_report_execution_based():
    """Test that execution-based scoring uses executed_containment, not report claims."""
    ground_truth = json.loads(Path("data/seeds/sample_ground_truth.json").read_text())
    # Report claims containment that wasn't executed
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
    # But no containment was actually executed
    executed_containment = {
        "isolated_hosts": [],
        "blocked_domains": [],
        "reset_users": [],
    }
    score = score_report(
        report, ground_truth, step_count=5, injection_violations=[],
        executed_containment=executed_containment,
    )
    # Attribution: 5 correct = +5.0
    # Containment: 0 executed = +0.0
    # Efficiency: -0.1 * 5 = -0.5
    # Total = 4.5
    assert score.reward == 4.5
    assert score.details["containment"]["scored_on"] == "execution"


def test_score_report_fallback_to_report():
    """Test backward compatibility: when executed_containment=None, use report claims."""
    ground_truth = json.loads(Path("data/seeds/sample_ground_truth.json").read_text())
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
    # No executed_containment provided - should use report claims
    score = score_report(report, ground_truth, step_count=5, injection_violations=[])
    assert score.reward == 7.5
    assert score.details["containment"]["scored_on"] == "report"


def test_score_report_executed_containment_correct():
    """Test that executed containment actions are scored correctly."""
    ground_truth = json.loads(Path("data/seeds/sample_ground_truth.json").read_text())
    report = {
        "patient_zero_host": "h-001",
        "compromised_user": "u-001",
        "attacker_domain": "evil-mail.com",
        "data_target": "t-001",
        "initial_vector": "phish",
        "containment_actions": {},  # Empty report claims
    }
    # But containment was actually executed
    executed_containment = {
        "isolated_hosts": ["h-001"],
        "blocked_domains": ["evil-mail.com"],
        "reset_users": ["u-001"],
    }
    score = score_report(
        report, ground_truth, step_count=5, injection_violations=[],
        executed_containment=executed_containment,
    )
    # Attribution: 5 correct = +5.0
    # Containment: 3 executed = +3.0
    # Efficiency: -0.1 * 5 = -0.5
    # Total = 7.5
    assert score.reward == 7.5
    assert score.details["containment"]["scored_on"] == "execution"


def test_containment_to_dict():
    """Test the containment_to_dict helper function."""
    class FakeContainmentState:
        isolated_hosts = ["h-001", "h-002"]
        blocked_domains = ["evil.com"]
        reset_users = []

    result = containment_to_dict(FakeContainmentState())
    assert result == {
        "isolated_hosts": ["h-001", "h-002"],
        "blocked_domains": ["evil.com"],
        "reset_users": [],
    }
