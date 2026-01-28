#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
from pathlib import Path as _Path

sys.path.append(str(_Path(__file__).resolve().parents[1]))

from scripts.validate_seed import validate_seed
from sim.log_compiler import compile_seed


def _load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/seeds/manifest.json")
    parser.add_argument("--split", choices=["train", "eval", "all"], default="all")
    parser.add_argument("--db-dir", default="data/sqlite/validate")
    args = parser.parse_args()

    manifest = _load_json(Path(args.manifest))
    splits = [args.split] if args.split != "all" else ["train", "eval"]

    db_dir = Path(args.db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    for split in splits:
        for entry in manifest[split]:
            seed_path = Path(entry["seed_path"])
            seed = _load_json(seed_path)
            errs = validate_seed(seed)
            if errs:
                errors += errs
                continue

            db_path = db_dir / f"{seed['scenario_id']}.db"
            try:
                compile_seed(seed_path, db_path)
            except Exception as exc:
                print(f"ERROR: log compile failed for {seed_path}: {exc}")
                errors += 1

    if errors > 0:
        print(f"Validation failed with {errors} error(s)")
        return 1

    print("OK: all seeds validated and compiled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
