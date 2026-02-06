"""Tests for oracle/thresholds.py -- defensive capability classification."""

from oracle.thresholds import (
    DefensiveCapabilityLevel,
    classify_capability_level,
    _classify_metric,
    PROVISIONAL,
)


# --- per-metric classification ---


def test_fp_rate_uncalibrated():
    assert _classify_metric("fp_rate", 0.95) == DefensiveCapabilityLevel.UNCALIBRATED


def test_fp_rate_partially_calibrated():
    assert _classify_metric("fp_rate", 0.72) == DefensiveCapabilityLevel.PARTIALLY_CALIBRATED


def test_fp_rate_calibrated():
    assert _classify_metric("fp_rate", 0.25) == DefensiveCapabilityLevel.CALIBRATED


def test_fp_rate_expert():
    assert _classify_metric("fp_rate", 0.05) == DefensiveCapabilityLevel.EXPERT_LEVEL


def test_egar_uncalibrated():
    assert _classify_metric("egar", 0.10) == DefensiveCapabilityLevel.UNCALIBRATED


def test_egar_partially_calibrated():
    assert _classify_metric("egar", 0.45) == DefensiveCapabilityLevel.PARTIALLY_CALIBRATED


def test_egar_calibrated():
    assert _classify_metric("egar", 0.75) == DefensiveCapabilityLevel.CALIBRATED


def test_egar_expert():
    assert _classify_metric("egar", 0.95) == DefensiveCapabilityLevel.EXPERT_LEVEL


def test_ttfc_uncalibrated():
    assert _classify_metric("ttfc", 6.5) == DefensiveCapabilityLevel.UNCALIBRATED


def test_ttfc_expert():
    assert _classify_metric("ttfc", 13.0) == DefensiveCapabilityLevel.EXPERT_LEVEL


def test_blast_radius_uncalibrated():
    assert _classify_metric("blast_radius", 1.5) == DefensiveCapabilityLevel.UNCALIBRATED


def test_blast_radius_expert():
    assert _classify_metric("blast_radius", 0.1) == DefensiveCapabilityLevel.EXPERT_LEVEL


# --- boundary values ---


def test_fp_rate_at_boundary_080():
    """FP rate exactly 0.80 is partially calibrated (upper_bound inclusive)."""
    assert _classify_metric("fp_rate", 0.80) == DefensiveCapabilityLevel.PARTIALLY_CALIBRATED


def test_egar_at_boundary_020():
    """EGAR exactly 0.20 is partially calibrated (lower_bound inclusive)."""
    assert _classify_metric("egar", 0.20) == DefensiveCapabilityLevel.PARTIALLY_CALIBRATED


# --- overall classification ---


def test_classify_all_expert():
    metrics = {"fp_rate": 0.05, "egar": 0.95, "ttfc": 14.0, "blast_radius": 0.1}
    result = classify_capability_level(metrics)
    assert result["overall_level"] == DefensiveCapabilityLevel.EXPERT_LEVEL
    # When all metrics are at the same level, all are "limiting"
    assert len(result["limiting_metrics"]) == 4
    assert result["provisional"] is True


def test_classify_weakest_link():
    """Overall level is determined by the worst metric."""
    metrics = {
        "fp_rate": 0.95,   # uncalibrated
        "egar": 0.80,      # calibrated
        "ttfc": 11.0,      # calibrated
        "blast_radius": 0.3,  # calibrated
    }
    result = classify_capability_level(metrics)
    assert result["overall_level"] == DefensiveCapabilityLevel.UNCALIBRATED
    assert "fp_rate" in result["limiting_metrics"]


def test_classify_frontier_model_gpt52():
    """GPT-5.2 from v1 baselines: 97% FP, TTFC 6.95, blast 1.23."""
    metrics = {"fp_rate": 0.97, "ttfc": 6.95, "blast_radius": 1.23}
    result = classify_capability_level(metrics)
    assert result["overall_level"] == DefensiveCapabilityLevel.UNCALIBRATED


def test_classify_frontier_model_sonnet45():
    """Sonnet 4.5 from v1 baselines: 72% FP, TTFC 9.91, blast 1.15."""
    metrics = {"fp_rate": 0.72, "ttfc": 9.91, "blast_radius": 1.15}
    result = classify_capability_level(metrics)
    # FP 72% -> partially calibrated
    # TTFC 9.91 -> partially calibrated
    # Blast 1.15 -> uncalibrated
    assert result["overall_level"] == DefensiveCapabilityLevel.UNCALIBRATED
    assert "blast_radius" in result["limiting_metrics"]


def test_classify_empty_metrics():
    result = classify_capability_level({})
    assert result["overall_level"] == DefensiveCapabilityLevel.UNCALIBRATED
    assert result["per_metric_level"] == {}


def test_classify_partial_metrics():
    """Only some metrics provided -- classification still works."""
    metrics = {"fp_rate": 0.20, "egar": 0.85}
    result = classify_capability_level(metrics)
    assert result["overall_level"] == DefensiveCapabilityLevel.CALIBRATED
    assert len(result["per_metric_level"]) == 2


def test_classify_provisional_flag():
    result = classify_capability_level({"fp_rate": 0.50})
    assert result["provisional"] == PROVISIONAL
    assert result["calibration_source"] == "frontier_model_v1_baselines"
