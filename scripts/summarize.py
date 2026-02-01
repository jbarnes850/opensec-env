#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load_manifest(manifest_path: Path) -> Dict[str, Dict[str, str]]:
    """Load manifest and create lookup by seed_path."""
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    lookup = {}
    for split in ("train", "eval"):
        for entry in manifest.get(split, []):
            lookup[entry["seed_path"]] = {
                "tier": entry.get("tier", "unknown"),
                "taxonomy_family": entry.get("taxonomy_family", "unknown"),
                "taxonomy_id": entry.get("taxonomy_id", "unknown"),
            }
    return lookup


def _mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, math.sqrt(var)


def _compute_group_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute metrics for a group of traces."""
    n = len(rows)
    if n == 0:
        return {}

    rewards = [r.get("reward", 0.0) for r in rows]
    diag = [r.get("diagnostics", {}) for r in rows]
    containment = [d.get("containment_attempted", False) for d in diag]
    fp_counts = [r.get("containment_false_positive_total", 0) for r in rows]

    # Injection violations from details
    inj_violations = 0
    for r in rows:
        details = r.get("details", {})
        inj = details.get("injection", {})
        if inj.get("violations"):
            inj_violations += 1

    return {
        "episodes": n,
        "reward": sum(rewards) / n,
        "cont_rate": sum(1 for c in containment if c) / n,
        "fp_rate": sum(1 for fp in fp_counts if fp > 0) / n,
        "inj_rate": inj_violations / n,
    }


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


def summarize_stratified(
    paths: List[Path],
    stratify_by: str,
    manifest_path: Path,
) -> None:
    """Summarize traces grouped by stratification key."""
    manifest_lookup = _load_manifest(manifest_path)

    # Load all traces and enrich with manifest data
    all_rows: List[Dict[str, Any]] = []
    for path in paths:
        rows = _load_jsonl(path)
        for row in rows:
            seed_path = row.get("seed_path", "")
            meta = manifest_lookup.get(seed_path, {})
            row["_tier"] = meta.get("tier", "unknown")
            row["_taxonomy_family"] = meta.get("taxonomy_family", "unknown")
            row["_taxonomy_id"] = meta.get("taxonomy_id", "unknown")
            all_rows.append(row)

    if not all_rows:
        print("No traces found")
        return

    # Group by model, then by stratification key
    by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        model = row.get("model", "unknown")
        by_model[model].append(row)

    # Map stratify_by to internal field
    strat_field = f"_{stratify_by}"

    for model, rows in sorted(by_model.items()):
        print(f"\nModel: {model}")

        # Group by stratification key
        by_strat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = row.get(strat_field, "unknown")
            by_strat[key].append(row)

        # Print table header
        print(f"  {stratify_by:15} | episodes | reward | cont_rate | fp_rate | inj_rate")
        print(f"  {'-'*15}-|----------|--------|-----------|---------|----------")

        # Print rows
        for strat_key in sorted(by_strat.keys()):
            group_rows = by_strat[strat_key]
            m = _compute_group_metrics(group_rows)
            print(
                f"  {strat_key:15} | {m['episodes']:>8} | {m['reward']:>6.2f} | "
                f"{m['cont_rate']:>9.2f} | {m['fp_rate']:>7.2f} | {m['inj_rate']:>8.2f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="JSONL files to summarize")
    parser.add_argument("--glob", default=None, help="Glob pattern (alternative to positional args)")
    parser.add_argument("--output", default="outputs/baseline_summary.json")
    parser.add_argument("--manifest", default="data/seeds/manifest.json", help="Seed manifest for metadata")
    parser.add_argument(
        "--stratify-by",
        choices=["taxonomy_family", "tier"],
        help="Group results by seed property",
    )
    args = parser.parse_args()

    if args.files:
        paths = [Path(f) for f in args.files]
    elif args.glob:
        paths = sorted(Path(".").glob(args.glob))
    else:
        paths = sorted(Path("outputs").glob("llm_baselines*.jsonl"))

    if args.stratify_by:
        summarize_stratified(paths, args.stratify_by, Path(args.manifest))
        return 0

    summary = summarize(paths)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
