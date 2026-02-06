import json
import tempfile
from pathlib import Path

import pytest
from training.curriculum import FlatCurriculum, StagedCurriculum, create_curriculum


@pytest.fixture
def tiered_manifest(tmp_path):
    manifest = {
        "train": [
            {"seed_path": "train/seed-001.json", "tier": "standard"},
            {"seed_path": "train/seed-002.json", "tier": "standard"},
        ],
        "eval": [
            {"seed_path": "eval/trivial-001.json", "tier": "trivial"},
            {"seed_path": "eval/trivial-002.json", "tier": "trivial"},
            {"seed_path": "eval/easy-001.json", "tier": "easy"},
            {"seed_path": "eval/easy-002.json", "tier": "easy"},
            {"seed_path": "eval/standard-001.json", "tier": "standard"},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    return str(manifest_path)


@pytest.fixture
def flat_manifest(tmp_path):
    manifest = {
        "train": [
            {"seed_path": "train/seed-001.json", "tier": "standard"},
            {"seed_path": "train/seed-002.json", "tier": "standard"},
            {"seed_path": "train/seed-003.json", "tier": "standard"},
        ],
        "eval": [],
    }
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    return str(manifest_path)


def test_staged_curriculum_with_eval_tiers(tiered_manifest):
    curriculum = StagedCurriculum(tiered_manifest, epochs_per_stage=1, use_eval_for_curriculum=True)
    assert curriculum.current_tier == "trivial"
    assert curriculum.has_tiered_data()
    counts = curriculum.tier_seed_counts()
    assert counts["trivial"] == 2
    assert counts["easy"] == 2
    assert counts["standard"] == 1


def test_staged_curriculum_advances(tiered_manifest):
    curriculum = StagedCurriculum(tiered_manifest, epochs_per_stage=1, use_eval_for_curriculum=True)
    assert curriculum.current_tier == "trivial"
    curriculum.advance_epoch()
    assert curriculum.current_tier == "easy"
    curriculum.advance_epoch()
    assert curriculum.current_tier == "standard"
    curriculum.advance_epoch()
    assert curriculum.is_complete


def test_staged_curriculum_multiple_epochs_per_stage(tiered_manifest):
    curriculum = StagedCurriculum(tiered_manifest, epochs_per_stage=2, use_eval_for_curriculum=True)
    curriculum.advance_epoch()
    assert curriculum.current_tier == "trivial"
    curriculum.advance_epoch()
    assert curriculum.current_tier == "easy"


def test_staged_curriculum_get_seeds(tiered_manifest):
    curriculum = StagedCurriculum(tiered_manifest, epochs_per_stage=1, use_eval_for_curriculum=True)
    seeds = curriculum.get_current_seeds()
    assert len(seeds) == 2
    assert all("trivial" in s for s in seeds)


def test_flat_curriculum(flat_manifest):
    curriculum = FlatCurriculum(flat_manifest, num_epochs=2)
    assert curriculum.current_tier == "standard"
    seeds = curriculum.get_current_seeds()
    assert len(seeds) == 3
    curriculum.advance_epoch()
    assert not curriculum.is_complete
    curriculum.advance_epoch()
    assert curriculum.is_complete


def test_create_curriculum_flat_when_no_tiers(flat_manifest):
    curriculum = create_curriculum(flat_manifest, use_curriculum=True)
    assert isinstance(curriculum, FlatCurriculum)


def test_create_curriculum_staged_with_eval(tiered_manifest):
    curriculum = create_curriculum(tiered_manifest, use_curriculum=True, use_eval_for_curriculum=True)
    assert isinstance(curriculum, StagedCurriculum)


def test_create_curriculum_disabled(tiered_manifest):
    curriculum = create_curriculum(tiered_manifest, use_curriculum=False)
    assert isinstance(curriculum, FlatCurriculum)
