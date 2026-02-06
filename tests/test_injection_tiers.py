"""Tests for injection CSV tier annotations."""

import csv
from pathlib import Path

CSV_PATH = Path("data/sources/prompt_injections.csv")


def _load_rows():
    with CSV_PATH.open() as f:
        return list(csv.DictReader(f))


def test_csv_has_difficulty_tier_column():
    rows = _load_rows()
    assert len(rows) > 0
    assert "difficulty_tier" in rows[0], f"Missing difficulty_tier column. Keys: {list(rows[0].keys())}"


def test_all_rows_have_valid_tier():
    rows = _load_rows()
    for row in rows:
        tier = row["difficulty_tier"]
        assert tier in ("1", "2", "3"), f"Invalid tier '{tier}' for {row['id']}"


def test_total_payload_count():
    rows = _load_rows()
    assert len(rows) == 82, f"Expected 82 payloads, got {len(rows)}"


def test_tier_distribution():
    rows = _load_rows()
    tiers = {"1": 0, "2": 0, "3": 0}
    for row in rows:
        tiers[row["difficulty_tier"]] += 1
    # Tier 1: ~20 (obvious overrides)
    assert tiers["1"] >= 15, f"Tier 1 too small: {tiers['1']}"
    # Tier 2: ~32 (contextualized)
    assert tiers["2"] >= 20, f"Tier 2 too small: {tiers['2']}"
    # Tier 3: ~30 (multi-step/complex)
    assert tiers["3"] >= 20, f"Tier 3 too small: {tiers['3']}"
    # No tier should dominate excessively
    assert all(t >= 15 for t in tiers.values()), f"Imbalanced tiers: {tiers}"


def test_tier1_are_simple_overrides():
    """Tier 1 payloads should be simple instruction overrides or hijacking."""
    rows = _load_rows()
    tier1_cats = {"Instruction Override", "Hijacking", "Formatting Trick"}
    tier1 = [r for r in rows if r["difficulty_tier"] == "1"]
    for row in tier1:
        assert row["complexity"] == "Simple", (
            f"{row['id']} is Tier 1 but complexity={row['complexity']}"
        )
        assert row["category"] in tier1_cats, (
            f"{row['id']} is Tier 1 but category={row['category']}"
        )


def test_tier3_are_complex_or_special():
    """Tier 3 payloads should be complex, jailbreaks, multilingual, or high effectiveness."""
    rows = _load_rows()
    tier3_cats = {"Jailbreak", "Multilingual"}
    tier3 = [r for r in rows if r["difficulty_tier"] == "3"]
    for row in tier3:
        is_complex = row["complexity"] == "Complex"
        is_special_cat = row["category"] in tier3_cats
        is_high_eff = row["effectiveness"] == "High"
        assert is_complex or is_special_cat or is_high_eff, (
            f"{row['id']} is Tier 3 but doesn't meet any criteria: "
            f"complexity={row['complexity']}, category={row['category']}, "
            f"effectiveness={row['effectiveness']}"
        )


def test_unique_ids():
    rows = _load_rows()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {len(ids)} total, {len(set(ids))} unique"
