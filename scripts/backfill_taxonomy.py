#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


CONTAINMENT_ACTIONS = {"block_domain", "isolate_host", "reset_user"}
QUERY_ACTIONS = {"query_logs", "submit_report"}
TAXONOMY_VERSION = "v1"
INJECTION_CSV = Path("data/sources/prompt_injections.csv")


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


def _first_trust(entries: List[Dict[str, Any]]) -> Optional[str]:
    for entry in entries:
        tier = entry.get("trust_tier")
        if tier:
            return tier
    return None


def _trust_profile(seed: Dict[str, Any]) -> Dict[str, str]:
    emails = seed.get("seed_artifacts", {}).get("emails", [])
    templates = seed.get("seed_artifacts", {}).get("log_templates", [])
    alert_templates = [t for t in templates if t.get("table") == "alerts"]
    log_templates = [t for t in templates if t.get("table") != "alerts"]
    return {
        "email": _first_trust(emails) or "unknown",
        "alert": _first_trust(alert_templates) or "unknown",
        "log": _first_trust(log_templates) or "unknown",
    }


def _objective_profile(seed: Dict[str, Any]) -> List[str]:
    graph = seed.get("attack_graph") or {}
    if graph.get("objectives"):
        return list(graph["objectives"])
    return []


def _classify_pattern(family: str, primary_action: str) -> str:
    if primary_action in CONTAINMENT_ACTIONS:
        group = "containment"
    elif primary_action in QUERY_ACTIONS:
        group = "query"
    else:
        group = "mixed"
    return f"{family}-{group}"


def _backfill_taxonomy(seed: Dict[str, Any]) -> Dict[str, Any]:
    metadata = seed.setdefault("metadata", {})
    if metadata.get("taxonomy"):
        return seed

    scenario_id = seed.get("scenario_id", "")
    if scenario_id.startswith("trivial-"):
        taxonomy = {
            "version": TAXONOMY_VERSION,
            "pattern_id": "trivial-explicit",
            "family": "trivial",
            "primary_action": "block_domain",
            "surfaces": ["email", "alert"],
            "objective_profile": ["exfil"],
            "trust_profile": _trust_profile(seed),
            "notes": "Single-step attribution with explicit alert evidence.",
        }
        metadata["taxonomy"] = taxonomy
        return seed
    if scenario_id.startswith("easy-"):
        taxonomy = {
            "version": TAXONOMY_VERSION,
            "pattern_id": "easy-auth-alert",
            "family": "easy",
            "primary_action": "block_domain",
            "surfaces": ["email", "log", "alert"],
            "objective_profile": ["access", "exfil"],
            "trust_profile": _trust_profile(seed),
            "notes": "Two-hop evidence with auth log + exfil alert attribution.",
        }
        metadata["taxonomy"] = taxonomy
        return seed

    payloads = seed.get("prompt_injection_payloads", [])
    surfaces = sorted({p.get("surface") for p in payloads if p.get("surface")})
    family = "benign"
    primary_action = None
    if payloads:
        for payload in payloads:
            if payload.get("injection_type"):
                family = payload["injection_type"]
                break
        for payload in payloads:
            if payload.get("target_action"):
                primary_action = payload["target_action"]
                break
    if not primary_action:
        primary_action = "query_logs"

    metadata["taxonomy"] = {
        "version": TAXONOMY_VERSION,
        "pattern_id": _classify_pattern(family, primary_action),
        "family": family,
        "primary_action": primary_action,
        "surfaces": surfaces,
        "objective_profile": _objective_profile(seed),
        "trust_profile": _trust_profile(seed),
        "notes": "Backfilled from injection metadata.",
    }
    return seed


def _load_injection_tiers(csv_path: Path) -> Dict[str, int]:
    """Load injection_id -> difficulty_tier mapping from the annotated CSV."""
    tier_map: Dict[str, int] = {}
    if not csv_path.exists():
        return tier_map
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            injection_id = row.get("id", "")
            tier_raw = row.get("difficulty_tier", "1")
            try:
                tier_map[injection_id] = int(tier_raw)
            except (ValueError, TypeError):
                tier_map[injection_id] = 1
    return tier_map


# Injection type -> difficulty tier mapping for existing seeds.
# Seed payloads don't store original CSV IDs (they compose CSV text
# with wrapping templates), so we classify by injection_type:
#   data_exfil: simple query goal -> Tier 1
#   direct_harm: authority-impersonating containment commands -> Tier 2
#   adaptive: multi-step with retry logic -> Tier 3
INJECTION_TYPE_TIER = {
    "data_exfil": 1,
    "direct_harm": 2,
    "adaptive": 3,
}


def _backfill_injection_tiers(
    seed: Dict[str, Any], tier_map: Dict[str, int]
) -> bool:
    """Add difficulty_tier to prompt_injection_payloads entries.

    First tries direct injection_id lookup in the CSV tier map (works
    for newly generated seeds that store CSV IDs). Falls back to
    classification by injection_type for existing seeds.

    Returns True if any payload was updated.
    """
    payloads = seed.get("prompt_injection_payloads", [])
    if not payloads:
        return False

    updated = False
    max_tier = 0
    for payload in payloads:
        if "difficulty_tier" in payload:
            max_tier = max(max_tier, payload["difficulty_tier"])
            continue

        injection_id = payload.get("injection_id", "")
        if injection_id in tier_map:
            payload["difficulty_tier"] = tier_map[injection_id]
        else:
            # Fallback: classify by injection_type
            inj_type = payload.get("injection_type", "")
            payload["difficulty_tier"] = INJECTION_TYPE_TIER.get(inj_type, 2)

        max_tier = max(max_tier, payload["difficulty_tier"])
        updated = True

    if updated:
        metadata = seed.setdefault("metadata", {})
        taxonomy = metadata.setdefault("taxonomy", {})
        taxonomy["injection_difficulty_tier"] = max_tier
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/seeds/manifest.json")
    parser.add_argument("--write", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--update-manifest", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--injection-csv", default=str(INJECTION_CSV))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = _load_json(manifest_path)
    tier_map = _load_injection_tiers(Path(args.injection_csv))

    tier_count = 0
    for split in ("train", "eval"):
        for entry in manifest.get(split, []):
            seed_path = Path(entry["seed_path"])
            seed = _load_json(seed_path)
            seed = _backfill_taxonomy(seed)
            if tier_map:
                if _backfill_injection_tiers(seed, tier_map):
                    tier_count += 1
            taxonomy = seed.get("metadata", {}).get("taxonomy", {})
            if args.write:
                _write_json(seed_path, seed)
            if args.update_manifest:
                entry["taxonomy_id"] = taxonomy.get("pattern_id")
                entry["taxonomy_family"] = taxonomy.get("family")
                if "injection_difficulty_tier" in taxonomy:
                    entry["injection_difficulty_tier"] = taxonomy["injection_difficulty_tier"]

    if args.update_manifest:
        _write_json(manifest_path, manifest)

    print(f"OK: taxonomy backfilled, {tier_count} seeds updated with injection tiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
