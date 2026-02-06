#!/usr/bin/env python3
"""Upload OpenSec seeds and baseline traces to HuggingFace Datasets Hub.

Usage:
    python scripts/upload_dataset_to_hf.py --dry-run  # Build files without uploading
    python scripts/upload_dataset_to_hf.py            # Upload to HuggingFace
    python scripts/upload_dataset_to_hf.py --include-baselines  # Include baseline traces
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional


def load_manifest(manifest_path: Path) -> dict:
    """Load and parse the manifest file."""
    with open(manifest_path) as f:
        return json.load(f)


def build_jsonl_rows(manifest: dict, base_dir: Path, split: str) -> list[dict]:
    """Convert manifest entries to JSONL rows.

    Note: seed and ground_truth are serialized as JSON strings to avoid
    HuggingFace Arrow schema casting issues with mixed-type nested dicts
    (e.g., attack_graph.states[*].actions[*].effects contains both bools and strings).
    """
    rows = []
    for entry in manifest[split]:
        seed_path = base_dir / entry["seed_path"]
        gt_path = base_dir / entry["ground_truth_path"]

        with open(seed_path) as f:
            seed_data = json.load(f)
        with open(gt_path) as f:
            gt_data = json.load(f)

        # Extract seed_id from scenario_id in seed data
        seed_id = seed_data.get("scenario_id", seed_path.stem.replace("_seed", ""))

        row = {
            "seed_id": seed_id,
            "split": split,
            "tier": entry["tier"],
            "taxonomy_family": entry["taxonomy_family"],
            "taxonomy_id": entry["taxonomy_id"],
            # Serialize complex nested objects as JSON strings for HF compatibility
            "seed_json": json.dumps(seed_data, separators=(",", ":")),
            "ground_truth_json": json.dumps(gt_data, separators=(",", ":")),
        }
        rows.append(row)
    return rows


def write_jsonl(rows: list[dict], output_path: Path) -> None:
    """Write rows to JSONL file."""
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_seed_manifest_lookup(manifest_path: Path) -> dict:
    """Build a lookup from scenario_id to tier/taxonomy info."""
    with open(manifest_path) as f:
        manifest = json.load(f)

    lookup = {}
    for split in ["train", "eval"]:
        for entry in manifest.get(split, []):
            # Extract seed_id from path like "data/seeds/eval/seed-161_seed.json"
            seed_path = Path(entry["seed_path"])
            seed_id = seed_path.stem.replace("_seed", "")
            lookup[seed_id] = {
                "tier": entry.get("tier", "standard"),
                "taxonomy_family": entry.get("taxonomy_family", "unknown"),
                "taxonomy_id": entry.get("taxonomy_id", "unknown"),
            }
    return lookup


def build_baseline_rows(
    baseline_manifest: dict,
    base_dir: Path,
    seed_lookup: dict,
) -> dict[str, list[dict]]:
    """Convert baseline trace files to JSONL rows grouped by model.

    Returns a dict mapping model_id to list of rows for that model's split.
    """
    results = {}

    for baseline in baseline_manifest["baselines"]:
        model_id = baseline["model_id"]
        model_name = baseline["model_name"]
        provider = baseline["provider"]
        rows = []

        for trace_path_str in baseline["traces"]:
            trace_path = base_dir / trace_path_str
            if not trace_path.exists():
                print(f"Warning: Trace file not found: {trace_path}")
                continue

            # Determine run_id from filename (h1 or h2)
            run_id = "h1" if "_h1" in trace_path.name else "h2"

            with open(trace_path) as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        trace = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Skipping malformed JSON at {trace_path.name}:{line_num}: {e}")
                        continue
                    scenario_id = trace.get("scenario_id", "unknown")

                    # Get tier/taxonomy from seed manifest lookup
                    seed_info = seed_lookup.get(scenario_id, {
                        "tier": "standard",
                        "taxonomy_family": "unknown",
                        "taxonomy_id": "unknown",
                    })

                    # Compute summary metrics
                    details = trace.get("details", {})
                    containment = details.get("containment", {})

                    # Count false positives across all containment categories
                    fp_count = 0
                    correct_count = 0
                    for field in ["isolated_hosts", "blocked_domains", "reset_users"]:
                        field_data = containment.get(field, {})
                        fp_count += len(field_data.get("false_positive", []))
                        correct_count += len(field_data.get("correct", []))

                    has_containment = bool(
                        trace.get("executed_containment", {}).get("isolated_hosts") or
                        trace.get("executed_containment", {}).get("blocked_domains") or
                        trace.get("executed_containment", {}).get("reset_users")
                    )

                    # Check injection violations
                    injection_violations = details.get("injection", {}).get("violations", [])

                    row = {
                        "trace_id": f"{model_id}-{scenario_id}-{run_id}",
                        "model": model_name,
                        "model_id": model_id,
                        "provider": provider,
                        "run_id": run_id,
                        "scenario_id": scenario_id,
                        "tier": seed_info["tier"],
                        "taxonomy_family": seed_info["taxonomy_family"],
                        "step_count": trace.get("step_count", 0),
                        "reward": trace.get("reward", 0.0),
                        "submitted_report": trace.get("submitted_report", False),
                        "containment_attempted": has_containment,
                        "correct_containment_count": correct_count,
                        "false_positive_count": fp_count,
                        "injection_violation_count": len(injection_violations),
                        # Serialize complex objects as JSON strings for HF compatibility
                        "details_json": json.dumps(details, separators=(",", ":")),
                        "executed_containment_json": json.dumps(
                            trace.get("executed_containment", {}),
                            separators=(",", ":")
                        ),
                        "diagnostics_json": json.dumps(
                            trace.get("diagnostics", {}),
                            separators=(",", ":")
                        ),
                        "steps_json": json.dumps(
                            trace.get("steps", []),
                            separators=(",", ":")
                        ),
                    }
                    rows.append(row)

        results[model_id] = rows
        print(f"Built {len(rows)} rows for {model_id}")

    return results


def upload_dataset(
    repo_id: str,
    data_dir: Path,
    assets_dir: Path,
    readme_path: Path,
) -> None:
    """Upload dataset files to HuggingFace Hub."""
    from huggingface_hub import HfApi, upload_file, create_repo

    api = HfApi()

    # Create repo if it doesn't exist
    create_repo(repo_id, repo_type="dataset", exist_ok=True)
    print(f"Repository ready: https://huggingface.co/datasets/{repo_id}")

    # Upload data files
    for jsonl_file in sorted(data_dir.glob("*.jsonl")):
        print(f"Uploading {jsonl_file.name}...")
        upload_file(
            path_or_fileobj=str(jsonl_file),
            path_in_repo=f"data/{jsonl_file.name}",
            repo_id=repo_id,
            repo_type="dataset",
        )

    # Upload README
    print("Uploading README.md...")
    upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
    )

    # Upload pipeline diagram
    pipeline_img = assets_dir / "seed-generation-pipeline.jpeg"
    if pipeline_img.exists():
        print("Uploading seed-generation-pipeline.jpeg...")
        upload_file(
            path_or_fileobj=str(pipeline_img),
            path_in_repo="seed-generation-pipeline.jpeg",
            repo_id=repo_id,
            repo_type="dataset",
        )


def main():
    parser = argparse.ArgumentParser(description="Upload OpenSec seeds to HuggingFace")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/seeds/manifest.json"),
        help="Path to seed manifest.json",
    )
    parser.add_argument(
        "--baseline-manifest",
        type=Path,
        default=Path("data/baselines/manifest.json"),
        help="Path to baseline manifest.json",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default="Jarrodbarnes/opensec-seeds",
        help="HuggingFace dataset repository ID",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("hf_upload_staging"),
        help="Staging directory for generated files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build files without uploading",
    )
    parser.add_argument(
        "--include-baselines",
        action="store_true",
        help="Include baseline evaluation traces",
    )
    parser.add_argument(
        "--baselines-only",
        action="store_true",
        help="Only upload baseline traces (skip seeds)",
    )
    args = parser.parse_args()

    # Resolve paths relative to repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    manifest_path = repo_root / args.manifest
    output_dir = repo_root / args.output_dir
    assets_dir = repo_root / "assets"

    # Build JSONL files
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)

    # Build seed splits (unless baselines-only)
    if not args.baselines_only:
        print(f"Loading seed manifest from {manifest_path}...")
        manifest = load_manifest(manifest_path)

        for split in ["train", "eval"]:
            rows = build_jsonl_rows(manifest, repo_root, split)
            output_path = data_dir / f"{split}.jsonl"
            write_jsonl(rows, output_path)
            print(f"Wrote {len(rows)} rows to {output_path}")

    # Build baseline splits (if requested)
    baseline_manifest_path = repo_root / args.baseline_manifest
    if args.include_baselines or args.baselines_only:
        if not baseline_manifest_path.exists():
            print(f"Error: Baseline manifest not found: {baseline_manifest_path}")
            return

        print(f"\nLoading baseline manifest from {baseline_manifest_path}...")
        with open(baseline_manifest_path) as f:
            baseline_manifest = json.load(f)

        # Load seed manifest for tier/taxonomy lookup
        seed_lookup = load_seed_manifest_lookup(manifest_path)

        # Build baseline rows grouped by model
        baseline_splits = build_baseline_rows(baseline_manifest, repo_root, seed_lookup)

        # Merge all baselines into a single split
        all_baseline_rows = []
        for model_id, rows in baseline_splits.items():
            all_baseline_rows.extend(rows)

        output_path = data_dir / "baselines.jsonl"
        write_jsonl(all_baseline_rows, output_path)
        print(f"Wrote {len(all_baseline_rows)} total baseline traces to {output_path}")

    # Copy dataset card
    readme_src = repo_root / "hf_assets" / "dataset_card.md"
    readme_dst = output_dir / "README.md"
    if readme_src.exists():
        import shutil
        shutil.copy(readme_src, readme_dst)
        print(f"Copied dataset card to {readme_dst}")
    else:
        print(f"Warning: Dataset card not found at {readme_src}")
        return

    if args.dry_run:
        print("\n[DRY RUN] Files staged but not uploaded.")
        print(f"Staged files in: {output_dir}")
        return

    # Upload to HuggingFace
    print("\nUploading to HuggingFace...")
    upload_dataset(
        repo_id=args.repo_id,
        data_dir=data_dir,
        assets_dir=assets_dir,
        readme_path=readme_dst,
    )
    print(f"\nDataset uploaded: https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
