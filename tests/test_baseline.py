import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.run_oracle_baseline import run_baseline


def test_baseline_score_threshold():
    result = run_baseline(Path("data/seeds/sample_seed.json"), max_steps=5)
    assert result["reward"] >= 6.0
