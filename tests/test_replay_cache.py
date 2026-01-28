import json
import os
import sqlite3
from pathlib import Path

from sim.attacker_policy import (
    AttackerPolicyManager,
    MockAttackerPolicy,
    ReplayCache,
    hash_agent_action,
    hash_attacker_context,
)


def _init_db(db_path: Path) -> None:
    schema = Path("schemas/sqlite_schema.sql").read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
        conn.commit()


def test_replay_cache_roundtrip(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    _init_db(db_path)

    cache = ReplayCache(str(db_path))
    manager = AttackerPolicyManager(cache=cache)
    policy = MockAttackerPolicy()

    scenario = json.loads(Path("data/seeds/sample_seed.json").read_text())
    agent_action = {"action_type": "query_logs", "params": {"sql": "SELECT 1"}}
    action_hash = hash_agent_action(agent_action)
    context_hash = hash_attacker_context(None)

    prior_mode = os.environ.get("OPENSEC_REPLAY_MODE")
    os.environ["OPENSEC_REPLAY_MODE"] = "replay"
    try:
        decision = manager.decide(
            scenario_id="seed-001",
            step=0,
            attacker_state="phish_sent",
            agent_action=agent_action,
            policy=policy,
            scenario=scenario,
            model="mock",
            temperature=0.1,
        )
    finally:
        if prior_mode is None:
            os.environ.pop("OPENSEC_REPLAY_MODE", None)
        else:
            os.environ["OPENSEC_REPLAY_MODE"] = prior_mode

    cached = cache.get("seed-001", 0, "phish_sent", action_hash, context_hash)
    assert cached == decision

    prior_mode = os.environ.get("OPENSEC_REPLAY_MODE")
    os.environ["OPENSEC_REPLAY_MODE"] = "replay"
    try:
        decision2 = manager.decide(
            scenario_id="seed-001",
            step=0,
            attacker_state="phish_sent",
            agent_action=agent_action,
            policy=policy,
            scenario=scenario,
            model="mock",
            temperature=0.1,
        )
    finally:
        if prior_mode is None:
            os.environ.pop("OPENSEC_REPLAY_MODE", None)
        else:
            os.environ["OPENSEC_REPLAY_MODE"] = prior_mode

    assert decision2 == decision
