#!/usr/bin/env python3
import json
import sys
from pathlib import Path

try:
    import jsonschema
except Exception:
    jsonschema = None


def _load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def _validate(schema_path: Path, instance_path: Path) -> int:
    schema = _load_json(schema_path)
    instance = _load_json(instance_path)
    jsonschema.validate(instance=instance, schema=schema)
    print(f"OK: {instance_path}")
    return 0


def main():
    if jsonschema is None:
        print("jsonschema not installed; skipping schema validation")
        return 0

    seed_schema = Path("schemas/seed_schema.json")
    gt_schema = Path("schemas/ground_truth_schema.json")

    errors = 0
    for seed_path in Path("data/seeds").glob("*.json"):
        if "ground_truth" in seed_path.name:
            errors += _validate(gt_schema, seed_path)
        else:
            errors += _validate(seed_schema, seed_path)

    return errors


if __name__ == "__main__":
    sys.exit(main())
