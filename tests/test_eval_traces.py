import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eval as eval_script
from server.models import ActionResult, ContainmentState, Observation


class FakeEnvironment:
    def __init__(self, seed_path):
        self.max_steps = 2
        self.scenario = {}
        self.scenario_id = "trace-test"
        self.step_count = 0
        self.containment = ContainmentState()
        self.seen_evidence_ids = set()
        self.content_evidence_ids = set()
        self.actions = []

    def _result(self):
        return SimpleNamespace(
            observation=Observation(
                scenario_id=self.scenario_id,
                step_index=self.step_count,
                attacker_state="phish_sent",
                containment=self.containment,
                last_action_result=ActionResult(
                    ok=True,
                    message="result",
                    data={"text": f"evidence at step {self.step_count}"},
                ),
            ),
            info={"attacker_action": "wait", "injection_violations": []},
        )

    def reset(self):
        return self._result()

    def step(self, action):
        self.actions.append(action.model_dump())
        self.step_count += 1
        return self._result()


def test_episode_preserves_model_inputs_raw_output_and_observations(monkeypatch):
    env = FakeEnvironment("unused")
    monkeypatch.setattr(eval_script, "OpenSecEnvironment", lambda **kwargs: env)
    raw_outputs = [
        "This response is not valid action JSON.",
        json.dumps({"action_type": "submit_report", "params": {"summary_json": {"answer": "done"}}}),
    ]
    requests = []

    def infer(model, messages, temperature, max_tokens):
        requests.append(copy.deepcopy(messages))
        return raw_outputs[len(requests) - 1]

    monkeypatch.setattr(eval_script, "_call_openai", infer)
    result = eval_script.run_episode(Path("unused"), {"provider": "openai", "name": "stub"}, 2)
    saved = json.loads(json.dumps(result))

    assert saved["messages"][:2] == requests[0]
    assert saved["messages"][:4] == requests[1]
    assert len(requests[0]) == 2
    assert len(requests[1]) == 4
    assert len(saved["messages"]) == 6
    assert [step["model_text"] for step in saved["steps"]] == raw_outputs
    assert saved["messages"][2] == {"role": "assistant", "content": raw_outputs[0]}
    assert saved["steps"][0]["action"]["action_type"] == "query_logs"
    assert saved["steps"][0]["action"]["params"] == {"sql": "SELECT 1"}
    assert saved["steps"][0]["observation"]["last_action_result"]["data"] == {"text": "evidence at step 1"}
    assert json.loads(requests[1][-1]["content"])["last_action_result"] == saved["steps"][0]["observation"]["last_action_result"]
    assert saved["steps"][1]["observation"]["step_index"] == 2
    assert saved["fallback_step"] is None
    assert saved["submitted_report"] is True
    assert saved["step_count"] == len(saved["steps"]) == 2


@pytest.mark.parametrize("max_steps", [0, 1])
def test_fallback_is_saved_as_a_harness_action_without_a_model_turn(monkeypatch, max_steps):
    env = FakeEnvironment("unused")
    env.max_steps = max_steps
    monkeypatch.setattr(eval_script, "OpenSecEnvironment", lambda **kwargs: env)
    monkeypatch.setattr(eval_script, "_call_openai", lambda *args: "invalid response")

    result = eval_script.run_episode(Path("unused"), {"provider": "openai", "name": "stub"}, 2)
    saved = json.loads(json.dumps(result))
    fallback = saved["fallback_step"]

    assert fallback["source"] == "harness"
    assert fallback["action"] == env.actions[-1]
    assert fallback["action"]["action_type"] == "submit_report"
    assert fallback["action"]["params"]["summary_json"] == saved["report"]
    assert fallback["observation"]["step_index"] == max_steps + 1
    assert fallback["attacker_action"] == "wait"
    assert fallback["injection_violations"] == []
    assert "model_text" not in fallback
    assert len(saved["messages"]) == 2 + 2 * max_steps
    assert len(saved["steps"]) == max_steps
    assert saved["step_count"] == max_steps + 1
    assert saved["submitted_report"] is False
    assert saved["total_containment_actions"] == 0


def test_jsonl_export_keeps_transcript_and_fallback(monkeypatch, tmp_path):
    env = FakeEnvironment("unused")
    env.max_steps = 1
    monkeypatch.setattr(eval_script, "OpenSecEnvironment", lambda **kwargs: env)
    monkeypatch.setattr(eval_script, "_call_openai", lambda *args: "unparseable output")
    monkeypatch.setattr(eval_script, "load_env", lambda: None)
    config = tmp_path / "config.yaml"
    config.write_text("models:\n  - provider: openai\n    name: stub\n")
    seed = tmp_path / "trace_seed.json"
    ground_truth = tmp_path / "trace_ground_truth.json"
    ground_truth.write_text(json.dumps({"attribution": {}, "containment_requirements": {}}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"eval": [{"seed_path": str(seed)}]}))
    output = tmp_path / "trace.jsonl"
    summary = tmp_path / "summary.json"
    monkeypatch.setattr(sys, "argv", [
        "eval.py", "--config", str(config), "--manifest", str(manifest),
        "--output", str(output), "--summary", str(summary),
    ])

    assert eval_script.main() == 0
    [row] = [json.loads(line) for line in output.read_text().splitlines()]
    assert row["messages"][2] == {"role": "assistant", "content": "unparseable output"}
    assert row["steps"][0]["model_text"] == "unparseable output"
    assert row["steps"][0]["observation"]["last_action_result"]["data"] == {"text": "evidence at step 1"}
    assert row["fallback_step"]["source"] == "harness"
    assert row["fallback_step"]["observation"]["step_index"] == 2
    assert row["reward"] == 0.0
    assert row["details"]["failure"] == "no_report_submitted"
    assert json.loads(summary.read_text())["stub"]["runs"] == 1
