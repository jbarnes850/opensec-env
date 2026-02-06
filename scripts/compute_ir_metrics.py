#!/usr/bin/env python3
"""Post-process baseline JSONL files to compute IR-centric metrics.

Computes:
- Time-to-First-Containment (TTFC): step index of first containment action
- Time-to-Report (TTR): step index of submit_report action
- Blast Radius: aggregate false positive count per episode
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


CONTAINMENT_ACTIONS = ["isolate_host", "block_domain", "reset_user"]


def compute_episode_metrics(episode: dict[str, Any]) -> dict[str, Any]:
    """Compute IR metrics from a single episode."""
    steps = episode.get("steps", [])

    # Time-to-first-containment: index of first containment action
    ttfc = -1
    for i, step in enumerate(steps):
        action_type = step.get("action", {}).get("action_type")
        if action_type in CONTAINMENT_ACTIONS:
            ttfc = i
            break

    # Time-to-report: index of submit_report action
    ttr = -1
    for i, step in enumerate(steps):
        action_type = step.get("action", {}).get("action_type")
        if action_type == "submit_report":
            ttr = i
            break

    # Blast radius: false positives per containment type
    details = episode.get("details", {}).get("containment", {})
    fp_hosts = len(details.get("isolated_hosts", {}).get("false_positive", []))
    fp_domains = len(details.get("blocked_domains", {}).get("false_positive", []))
    fp_users = len(details.get("reset_users", {}).get("false_positive", []))

    return {
        "time_to_first_containment": ttfc,
        "time_to_report": ttr,
        "blast_radius_total": fp_hosts + fp_domains + fp_users,
        "blast_radius_hosts": fp_hosts,
        "blast_radius_domains": fp_domains,
        "blast_radius_users": fp_users,
    }


def aggregate_metrics(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate IR metrics across episodes."""
    ttfc_values = [e["time_to_first_containment"] for e in episodes if e["time_to_first_containment"] >= 0]
    ttr_values = [e["time_to_report"] for e in episodes if e["time_to_report"] >= 0]
    blast_values = [e["blast_radius_total"] for e in episodes]

    def safe_mean(vals: list[float]) -> float | None:
        return statistics.mean(vals) if vals else None

    def safe_median(vals: list[float]) -> float | None:
        return statistics.median(vals) if vals else None

    def safe_stdev(vals: list[float]) -> float | None:
        return statistics.stdev(vals) if len(vals) > 1 else None

    return {
        "total_episodes": len(episodes),
        "containment_attempted_count": len(ttfc_values),
        "containment_attempted_rate": len(ttfc_values) / len(episodes) if episodes else 0,
        "report_submitted_count": len(ttr_values),
        "report_submitted_rate": len(ttr_values) / len(episodes) if episodes else 0,
        "ttfc_mean": safe_mean(ttfc_values),
        "ttfc_median": safe_median(ttfc_values),
        "ttfc_stdev": safe_stdev(ttfc_values),
        "ttfc_min": min(ttfc_values) if ttfc_values else None,
        "ttfc_max": max(ttfc_values) if ttfc_values else None,
        "ttr_mean": safe_mean(ttr_values),
        "ttr_median": safe_median(ttr_values),
        "ttr_stdev": safe_stdev(ttr_values),
        "ttr_min": min(ttr_values) if ttr_values else None,
        "ttr_max": max(ttr_values) if ttr_values else None,
        "blast_radius_mean": safe_mean(blast_values),
        "blast_radius_median": safe_median(blast_values),
        "blast_radius_stdev": safe_stdev(blast_values),
        "blast_radius_max": max(blast_values) if blast_values else None,
        "blast_radius_total": sum(blast_values),
    }


def process_jsonl_file(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Process a single JSONL file and return enriched episodes + aggregate stats."""
    enriched_episodes = []
    model_name = None
    skipped = 0

    with input_path.open() as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                episode = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  Warning: skipping malformed line {line_num}: {e}")
                skipped += 1
                continue
            if model_name is None:
                model_name = episode.get("model", "unknown")

            ir_metrics = compute_episode_metrics(episode)
            enriched = {**episode, "ir_metrics": ir_metrics}
            enriched_episodes.append(enriched)

    ir_only = [e["ir_metrics"] for e in enriched_episodes]
    aggregate = aggregate_metrics(ir_only)
    aggregate["model"] = model_name
    aggregate["source_file"] = str(input_path)

    return enriched_episodes, aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute IR-centric metrics from JSONL episode files")
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Input JSONL file(s) to process (supports glob patterns)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output directory for enriched JSONL and summary (default: outputs)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only output summary, skip enriched JSONL files",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_summaries: dict[str, dict[str, Any]] = {}
    combined_episodes: list[dict[str, Any]] = []

    for input_pattern in args.input:
        input_path = Path(input_pattern)
        if not input_path.exists():
            print(f"Warning: {input_path} does not exist, skipping")
            continue

        print(f"Processing {input_path}...")
        enriched, aggregate = process_jsonl_file(input_path)
        combined_episodes.extend(enriched)

        model_key = aggregate["model"]
        if model_key in all_summaries:
            # Merge with existing (combine h1 + h2 halves)
            existing = all_summaries[model_key]
            existing["total_episodes"] += aggregate["total_episodes"]
            existing["containment_attempted_count"] += aggregate["containment_attempted_count"]
            existing["report_submitted_count"] += aggregate["report_submitted_count"]
            existing["blast_radius_total"] += aggregate["blast_radius_total"]
            existing["source_files"] = existing.get("source_files", [existing.get("source_file", "")]) + [
                aggregate["source_file"]
            ]
        else:
            all_summaries[model_key] = aggregate

        if not args.summary_only:
            out_jsonl = output_dir / f"{input_path.stem}_ir_enriched.jsonl"
            with out_jsonl.open("w") as f:
                for ep in enriched:
                    f.write(json.dumps(ep) + "\n")
            print(f"  Wrote {out_jsonl} ({len(enriched)} episodes)")

        print(f"  Model: {aggregate['model']}")
        print(f"  Episodes: {aggregate['total_episodes']}")
        print(f"  TTFC mean: {aggregate['ttfc_mean']:.2f}" if aggregate["ttfc_mean"] else "  TTFC: N/A")
        print(f"  TTR mean: {aggregate['ttr_mean']:.2f}" if aggregate["ttr_mean"] else "  TTR: N/A")
        print(f"  Blast radius mean: {aggregate['blast_radius_mean']:.2f}" if aggregate["blast_radius_mean"] else "")

    # Recompute aggregates for merged models
    for model_key, summary in all_summaries.items():
        summary["containment_attempted_rate"] = (
            summary["containment_attempted_count"] / summary["total_episodes"]
            if summary["total_episodes"]
            else 0
        )
        summary["report_submitted_rate"] = (
            summary["report_submitted_count"] / summary["total_episodes"] if summary["total_episodes"] else 0
        )

    # Recompute per-model stats from combined episodes
    for model_key in all_summaries:
        model_episodes = [e["ir_metrics"] for e in combined_episodes if e.get("model") == model_key]
        if model_episodes:
            recomputed = aggregate_metrics(model_episodes)
            all_summaries[model_key].update(
                {
                    k: v
                    for k, v in recomputed.items()
                    if k
                    not in ("total_episodes", "containment_attempted_count", "report_submitted_count", "blast_radius_total")
                }
            )

    # Write summary
    summary_path = output_dir / "ir_metrics_summary.json"
    with summary_path.open("w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\nWrote summary to {summary_path}")

    # Print comparison table
    print("\n" + "=" * 80)
    print("IR Metrics Comparison")
    print("=" * 80)
    print(f"{'Model':<30} {'TTFC':<12} {'TTR':<12} {'Blast Radius':<15} {'Episodes':<10}")
    print("-" * 80)
    for model_key, summary in sorted(all_summaries.items()):
        ttfc = f"{summary['ttfc_mean']:.2f}" if summary.get("ttfc_mean") else "N/A"
        ttr = f"{summary['ttr_mean']:.2f}" if summary.get("ttr_mean") else "N/A"
        blast = f"{summary['blast_radius_mean']:.2f}" if summary.get("blast_radius_mean") else "N/A"
        print(f"{model_key:<30} {ttfc:<12} {ttr:<12} {blast:<15} {summary['total_episodes']:<10}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
