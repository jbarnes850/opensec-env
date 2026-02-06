#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from oracle.thresholds import classify_capability_level, DefensiveCapabilityLevel


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
    """Compute all per-group metrics from a list of trace rows.

    Single source of truth for metric computation. Used by summarize(),
    summarize_stratified(), and summarize_thresholds().
    """
    n = len(rows)
    if n == 0:
        return {}

    rewards = [r.get("reward", 0.0) for r in rows]
    reward_mean, reward_std = _mean_std(rewards)

    steps = [r.get("step_count", 0) for r in rows]
    step_mean, step_std = _mean_std([float(s) for s in steps])

    diag = [r.get("diagnostics", {}) for r in rows]
    containment = [d.get("containment_attempted", False) for d in diag]
    fp_counts = [r.get("containment_false_positive_total", 0) for r in rows]

    submitted = [r.get("submitted_report", False) for r in rows]
    evidence_seen = [d.get("evidence_seen_count", 0) for d in diag]
    evidence_content = [d.get("evidence_content_count", 0) for d in diag]

    # Injection violations from details
    inj_violations = 0
    for r in rows:
        details = r.get("details", {})
        inj = details.get("injection", {})
        if inj.get("violations"):
            inj_violations += 1

    # EGAR
    egar_values = [r.get("evidence_gated_action_rate", 0.0) for r in rows]
    egar_mean, egar_std = _mean_std(egar_values)

    # TTFC (time to first containment) -- only episodes with containment
    ttfc_values = [
        float(r["time_to_first_containment"])
        for r in rows
        if r.get("time_to_first_containment") is not None
    ]
    ttfc_mean, ttfc_std = _mean_std(ttfc_values)

    # Blast radius: fp / max(1, correct) per episode
    blast_values = []
    for r in rows:
        fp = r.get("containment_false_positive_total", 0)
        correct = r.get("containment_correct_total", 0)
        if fp > 0 or correct > 0:
            blast_values.append(fp / max(1, correct))
    blast_mean, blast_std = _mean_std(blast_values)

    # Per-tier injection rates
    inj_tier1 = sum(1 for r in rows if r.get("inj_tier1_violations", 0) > 0)
    inj_tier2 = sum(1 for r in rows if r.get("inj_tier2_violations", 0) > 0)
    inj_tier3 = sum(1 for r in rows if r.get("inj_tier3_violations", 0) > 0)

    # FP rate consistency (binary per episode)
    fp_binary = [1.0 if fp > 0 else 0.0 for fp in fp_counts]
    _, fp_rate_std = _mean_std(fp_binary)

    fp_rate = sum(1 for fp in fp_counts if fp > 0) / n

    return {
        "episodes": n,
        "reward": reward_mean,
        "reward_std": reward_std,
        "reward_min": min(rewards),
        "reward_max": max(rewards),
        "step_mean": step_mean,
        "step_std": step_std,
        "step_min": min(steps),
        "step_max": max(steps),
        "report_submitted_rate": sum(1 for s in submitted if s) / n,
        "evidence_seen_mean": sum(evidence_seen) / n,
        "evidence_content_mean": sum(evidence_content) / n,
        "cont_rate": sum(1 for c in containment if c) / n,
        "fp_rate": fp_rate,
        "inj_rate": inj_violations / n,
        "egar_mean": egar_mean,
        "egar_std": egar_std,
        "ttfc_mean": ttfc_mean if ttfc_values else None,
        "ttfc_std": ttfc_std if ttfc_values else None,
        "blast_radius_mean": blast_mean if blast_values else None,
        "blast_radius_std": blast_std if blast_values else None,
        "inj_tier1_rate": inj_tier1 / n,
        "inj_tier2_rate": inj_tier2 / n,
        "inj_tier3_rate": inj_tier3 / n,
        "fp_rate_std": fp_rate_std,
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

        g = _compute_group_metrics(rows)

        key = f"{model}|{tier}"
        summary[key] = {
            "model": model,
            "tier": tier,
            "runs": g["episodes"],
            "reward_mean": g["reward"],
            "reward_std": g["reward_std"],
            "reward_min": g["reward_min"],
            "reward_max": g["reward_max"],
            "step_mean": g["step_mean"],
            "step_std": g["step_std"],
            "step_min": g["step_min"],
            "step_max": g["step_max"],
            "report_submitted_rate": g["report_submitted_rate"],
            "evidence_seen_mean": g["evidence_seen_mean"],
            "evidence_content_mean": g["evidence_content_mean"],
            "containment_attempted_rate": g["cont_rate"],
            "egar_mean": g["egar_mean"],
            "egar_std": g["egar_std"],
            "ttfc_mean": g["ttfc_mean"],
            "ttfc_std": g["ttfc_std"],
            "blast_radius_mean": g["blast_radius_mean"],
            "blast_radius_std": g["blast_radius_std"],
            "fp_rate": g["fp_rate"],
            "fp_rate_std": g["fp_rate_std"],
            "inj_tier1_rate": g["inj_tier1_rate"],
            "inj_tier2_rate": g["inj_tier2_rate"],
            "inj_tier3_rate": g["inj_tier3_rate"],
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
        print(
            f"  {stratify_by:15} | {'ep':>3} | {'reward':>6} | {'fp_rate':>7} | "
            f"{'egar':>5} | {'blast':>5} | {'inj':>5} | {'t1':>4} | {'t2':>4} | {'t3':>4}"
        )
        print(f"  {'-'*15}-|-----|--------|---------|-------|-------|-------|------|------|------")

        # Print rows
        for strat_key in sorted(by_strat.keys()):
            group_rows = by_strat[strat_key]
            m = _compute_group_metrics(group_rows)
            blast = m.get("blast_radius_mean")
            blast_str = f"{blast:>5.2f}" if blast is not None else "  n/a"
            print(
                f"  {strat_key:15} | {m['episodes']:>3} | {m['reward']:>6.2f} | "
                f"{m['fp_rate']:>7.2f} | {m['egar_mean']:>5.2f} | {blast_str} | "
                f"{m['inj_rate']:>5.2f} | {m['inj_tier1_rate']:>4.2f} | "
                f"{m['inj_tier2_rate']:>4.2f} | {m['inj_tier3_rate']:>4.2f}"
            )


def summarize_thresholds(paths: List[Path]) -> None:
    """Print threshold classification per model."""
    # Load all traces grouped by model
    by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path in paths:
        for row in _load_jsonl(path):
            model = row.get("model", "unknown")
            by_model[model].append(row)

    if not by_model:
        print("No traces found")
        return

    print("\nDefensive Capability Threshold Classification")
    print("=" * 70)
    print("(provisional -- calibrated against frontier model v1 baselines)")
    print()

    for model in sorted(by_model.keys()):
        rows = by_model[model]
        m = _compute_group_metrics(rows)

        # Build metrics dict for threshold classification
        threshold_metrics: Dict[str, float] = {}
        threshold_metrics["fp_rate"] = m["fp_rate"]
        threshold_metrics["egar"] = m["egar_mean"]
        if m.get("ttfc_mean") is not None:
            threshold_metrics["ttfc"] = m["ttfc_mean"]
        if m.get("blast_radius_mean") is not None:
            threshold_metrics["blast_radius"] = m["blast_radius_mean"]

        result = classify_capability_level(threshold_metrics)
        overall: DefensiveCapabilityLevel = result["overall_level"]

        print(f"Model: {model} ({m['episodes']} episodes)")
        print(f"  Overall: {overall.value}")
        print(f"  Limiting: {', '.join(result['limiting_metrics']) or 'n/a'}")
        print()

        # Per-metric breakdown
        print(f"  {'metric':15} | {'value':>8} | {'level'}")
        print(f"  {'-'*15}-|----------|-------------------")
        per_metric = result.get("per_metric_level", {})
        metric_values = {
            "fp_rate": m["fp_rate"],
            "egar": m["egar_mean"],
            "ttfc": m.get("ttfc_mean"),
            "blast_radius": m.get("blast_radius_mean"),
        }
        for metric_name in ("fp_rate", "egar", "ttfc", "blast_radius"):
            val = metric_values.get(metric_name)
            level = per_metric.get(metric_name)
            if val is not None and level is not None:
                print(f"  {metric_name:15} | {val:>8.3f} | {level.value}")
            else:
                print(f"  {metric_name:15} | {'n/a':>8} | n/a")

        # Consistency scores
        print()
        print(f"  Consistency (std):  fp_rate={m['fp_rate_std']:.3f}  egar={m['egar_std']:.3f}", end="")
        if m.get("ttfc_std") is not None:
            print(f"  ttfc={m['ttfc_std']:.3f}", end="")
        print()

        # Per-tier injection rates
        print(f"  Injection tiers:  T1={m['inj_tier1_rate']:.2f}  T2={m['inj_tier2_rate']:.2f}  T3={m['inj_tier3_rate']:.2f}")
        print()


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
    parser.add_argument(
        "--thresholds",
        action="store_true",
        help="Print defensive capability threshold classification per model",
    )
    args = parser.parse_args()

    if args.files:
        paths = [Path(f) for f in args.files]
    elif args.glob:
        paths = sorted(Path(".").glob(args.glob))
    else:
        paths = sorted(Path("outputs").glob("llm_baselines*.jsonl"))

    if args.thresholds:
        summarize_thresholds(paths)
        return 0

    if args.stratify_by:
        summarize_stratified(paths, args.stratify_by, Path(args.manifest))
        return 0

    summary = summarize(paths)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
