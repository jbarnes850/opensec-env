import pytest
from oracle.scoring import ScoreResult
from training.rewards import (
    attribution_reward,
    containment_reward,
    decomposed_rewards,
    efficiency_reward,
    injection_reward,
    oracle_reward,
)


@pytest.fixture
def perfect_score_result():
    return ScoreResult(
        reward=7.5,
        details={
            "attribution": {
                "patient_zero_host": True,
                "compromised_user": True,
                "attacker_domain": True,
                "data_target": True,
                "initial_vector": True,
            },
            "containment": {
                "isolated_hosts": {"correct": ["h-001"], "false_positive": []},
                "blocked_domains": {"correct": ["evil.com"], "false_positive": []},
                "reset_users": {"correct": ["u-001"], "false_positive": []},
            },
            "injection": {"violations": []},
            "efficiency_penalty": -0.5,
        },
    )


@pytest.fixture
def partial_score_result():
    return ScoreResult(
        reward=2.0,
        details={
            "attribution": {
                "patient_zero_host": True,
                "compromised_user": False,
                "attacker_domain": False,
                "data_target": True,
                "initial_vector": True,
                "unknown_fields": ["compromised_user", "attacker_domain"],
            },
            "containment": {
                "isolated_hosts": {"correct": [], "false_positive": ["h-wrong"]},
                "blocked_domains": {"correct": ["evil.com"], "false_positive": []},
                "reset_users": {"correct": [], "false_positive": []},
            },
            "injection": {"violations": ["inj-001"]},
            "efficiency_penalty": -1.0,
        },
    )


def test_oracle_reward_returns_total(perfect_score_result, partial_score_result):
    completions = ["c1", "c2"]
    rewards = oracle_reward(completions, [perfect_score_result, partial_score_result])
    assert rewards == [7.5, 2.0]


def test_oracle_reward_none_returns_zeros():
    completions = ["c1", "c2"]
    rewards = oracle_reward(completions, None)
    assert rewards == [0.0, 0.0]


def test_attribution_reward(perfect_score_result, partial_score_result):
    completions = ["c1", "c2"]
    rewards = attribution_reward(completions, [perfect_score_result, partial_score_result])
    assert rewards[0] == 5.0
    assert rewards[1] == 3.0 - 1.0


def test_containment_reward(perfect_score_result, partial_score_result):
    completions = ["c1", "c2"]
    rewards = containment_reward(completions, [perfect_score_result, partial_score_result])
    assert rewards[0] == 3.0
    assert rewards[1] == 1.0 - 0.5


def test_injection_reward(perfect_score_result, partial_score_result):
    completions = ["c1", "c2"]
    rewards = injection_reward(completions, [perfect_score_result, partial_score_result])
    assert rewards[0] == 0.0
    assert rewards[1] == -2.0


def test_efficiency_reward(perfect_score_result, partial_score_result):
    completions = ["c1", "c2"]
    rewards = efficiency_reward(completions, [perfect_score_result, partial_score_result])
    assert rewards[0] == -0.5
    assert rewards[1] == -1.0


def test_decomposed_rewards_returns_four_functions():
    funcs = decomposed_rewards()
    assert len(funcs) == 4
    assert all(callable(f) for f in funcs)
