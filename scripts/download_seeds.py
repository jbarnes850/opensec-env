#!/usr/bin/env python3
"""Download OpenSec seeds from HuggingFace to local data/seeds/ directory.

Usage:
    python scripts/download_seeds.py              # Download all seeds
    python scripts/download_seeds.py --split eval  # Download eval only
"""

import argparse
import json
from pathlib import Path


def download_seeds(
    repo_id: str,
    output_dir: Path,
    split: str | None = None,
) -> None:
    from huggingface_hub import hf_hub_download

    splits = [split] if split else ["train", "eval"]

    for s in splits:
        path = hf_hub_download(repo_id, f"data/{s}.jsonl", repo_type="dataset")
        seed_dir = output_dir / s
        seed_dir.mkdir(parents=True, exist_ok=True)

        with open(path) as f:
            rows = [json.loads(line) for line in f if line.strip()]

        for row in rows:
            seed_data = json.loads(row["seed_json"])
            gt_data = json.loads(row["ground_truth_json"])
            scenario_id = seed_data["scenario_id"]

            seed_path = seed_dir / f"{scenario_id}_seed.json"
            gt_path = seed_dir / f"{scenario_id}_ground_truth.json"

            seed_path.write_text(json.dumps(seed_data, indent=2) + "\n")
            gt_path.write_text(json.dumps(gt_data, indent=2) + "\n")

        print(f"  {s}: {len(rows)} seeds -> {seed_dir}/")

    # Rebuild manifest from downloaded seeds
    manifest = _build_manifest(output_dir)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(len(v) for v in manifest.values())
    print(f"  manifest: {total} entries -> {manifest_path}")


def _build_manifest(seeds_dir: Path) -> dict:
    """Build manifest.json from downloaded seed files."""
    manifest: dict[str, list] = {}
    for split_dir in sorted(seeds_dir.iterdir()):
        if not split_dir.is_dir():
            continue
        split = split_dir.name
        if split not in ("train", "eval"):
            continue
        entries = []
        for seed_file in sorted(split_dir.glob("*_seed.json")):
            with open(seed_file) as f:
                seed_data = json.load(f)
            gt_file = seed_file.with_name(
                seed_file.name.replace("_seed.json", "_ground_truth.json")
            )
            metadata = seed_data.get("metadata", {})
            taxonomy = metadata.get("taxonomy", {})
            entry = {
                "seed_path": str(Path("data/seeds") / split / seed_file.name),
                "ground_truth_path": str(Path("data/seeds") / split / gt_file.name),
                "tier": taxonomy.get("family", "standard"),
                "taxonomy_family": taxonomy.get("family", "unknown"),
                "taxonomy_id": taxonomy.get("pattern_id", "unknown"),
            }
            # Include injection tier if present
            payloads = seed_data.get("prompt_injection_payloads", [])
            tiers = [p.get("difficulty_tier") for p in payloads if p.get("difficulty_tier")]
            if tiers:
                entry["injection_difficulty_tier"] = max(tiers)
            entries.append(entry)
        manifest[split] = entries
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OpenSec seeds from HuggingFace")
    parser.add_argument(
        "--repo-id", default="Jarrodbarnes/opensec-seeds",
        help="HuggingFace dataset repo ID",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/seeds"),
        help="Local output directory",
    )
    parser.add_argument(
        "--split", choices=["train", "eval"], default=None,
        help="Download specific split (default: both)",
    )
    args = parser.parse_args()

    print(f"Downloading seeds from {args.repo_id}...")
    download_seeds(args.repo_id, args.output_dir, args.split)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
