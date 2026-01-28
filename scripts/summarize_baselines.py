#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, math.sqrt(var)


def summarize(paths: List[Path]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for path in paths:
        rows = _load_jsonl(path)
        if not rows:
            continue
        model = rows[0].get("model", "unknown")
        tier = "unknown"
        if "trivial" in path.name:
            tier = "trivial"
        elif "easy" in path.name:
            tier = "easy"
        elif "standard" in path.name:
            tier = "standard"

        rewards = [r.get("reward", 0.0) for r in rows]
        steps = [r.get("step_count", 0) for r in rows]
        submitted = [r.get("submitted_report", False) for r in rows]
        reward_mean, reward_std = _mean_std(rewards)
        step_mean, step_std = _mean_std([float(s) for s in steps])

        diag = [r.get("diagnostics", {}) for r in rows]
        evidence_seen = [d.get("evidence_seen_count", 0) for d in diag]
        evidence_content = [d.get("evidence_content_count", 0) for d in diag]
        containment_attempted = [d.get("containment_attempted", False) for d in diag]

        key = f"{model}|{tier}"
        summary[key] = {
            "model": model,
            "tier": tier,
            "runs": len(rows),
            "reward_mean": reward_mean,
            "reward_std": reward_std,
            "reward_min": min(rewards),
            "reward_max": max(rewards),
            "step_mean": step_mean,
            "step_std": step_std,
            "step_min": min(steps),
            "step_max": max(steps),
            "report_submitted_rate": sum(1 for s in submitted if s) / len(rows),
            "evidence_seen_mean": sum(evidence_seen) / len(rows),
            "evidence_content_mean": sum(evidence_content) / len(rows),
            "containment_attempted_rate": sum(1 for c in containment_attempted if c) / len(rows),
            "source_file": str(path),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", default="outputs/grid_*.jsonl")
    parser.add_argument("--output", default="outputs/baseline_grid_summary.json")
    args = parser.parse_args()

    paths = sorted(Path(".").glob(args.glob))
    summary = summarize(paths)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
