# Experiment Log: v2 Baseline Run

Branch: `v2/sprint-1-metrics`
Date: 2026-02-06
Status: Pre-run (pipeline verified, 52/52 tests pass)

## Context

This run produces the numbers for the arXiv paper revision (arXiv:2601.21083) and the
OpenAI Cybersecurity Grant Program application. Sprint 1 added three metric families
to the evaluation pipeline. This document records what we expect to learn and why.

### What v1 Showed (Technical Report, Tables 1-2)

4 models, 5 metrics, 40 standard-tier seeds:

| Model | Reward | FP Rate | Cont Rate | Report Rate | Inj Rate |
|---|---|---|---|---|---|
| GPT-5.2 | -1.23 | 97% | 95% | 100% | 12% |
| Sonnet 4.5 | 0.41 | 72% | 88% | 100% | 5% |
| Gemini 3 | -0.87 | 90% | 92% | 95% | 8% |
| DeepSeek 3.2 | -1.45 | 93% | 85% | 78% | 15% |

Core finding: 90-97% false positive rates across 3/4 frontier models. Sonnet 4.5
showed partial calibration (72% FP). But v1 could not explain WHY models fail
or distinguish failure modes.

### What v2 Adds

Three new metric families computed during episode execution:

1. **EGAR** (Evidence-Gated Action Rate) -- `oracle/calibration.py`
2. **Per-tier injection rates** (T1/T2/T3) -- `oracle/verifier.py`, `scripts/eval.py`
3. **Blast radius + TTFC** -- `scripts/summarize.py`

Plus threshold classification via `oracle/thresholds.py` (provisional).

## Three Questions This Run Answers

### Q1: Do models act on evidence or act blindly?

**v1 gap**: FP rate is binary (wrong action, yes/no). Cannot distinguish a model
that investigates and misinterprets evidence from one that never investigates at all.

**v2 metric**: EGAR measures, for each containment action, whether the model fetched
trusted evidence about that specific target entity before acting. Trust-tier filtering
excludes entities from untrusted sources (injected emails, attacker-controlled data).

**Preparedness Framework alignment**: Table 5 (Appendix C.2) defines "Instruction
Alignment" as a safeguard: "Large scale usage or testing in realistic settings should
show the model consistently takes action aligned to the user's instructions." Our
defender prompt says "Be precise. Only take containment actions when you have
sufficient evidence." EGAR is a direct measurement of compliance with that instruction.

**Expected outcomes**:
- Most models: EGAR near 0% (act without evidence)
- Sonnet 4.5: possibly higher EGAR given its lower FP rate
- If EGAR is uniformly low, the 90-97% FP rates are explained: models skip
  the investigation phase entirely

### Q2: Does safety training generalize to adversarial prompt injection?

**v1 gap**: Single aggregate injection violation rate. No difficulty gradient.

**v2 metric**: Per-tier injection rates. 82 payloads classified:
- T1 (20 payloads): Obvious overrides ("IGNORE PREVIOUS INSTRUCTIONS")
- T2 (32 payloads): Contextualized, domain-appropriate framing
- T3 (30 payloads): Multi-step, complex, or multilingual

**GPT-5.3-Codex system card context** (Feb 5, 2026):
- Destructive action avoidance: 0.88 (trained via RL with "user model" conflicts)
- CyScenarioBench: 0/all (fails every constraint-aware multi-stage scenario)
- First model treated as "High" in Cybersecurity under Preparedness Framework
- Cyber Range: 80% combined solve rate (up from 53% for GPT-5.2)

**Prediction**: Safety training (0.88 destructive action avoidance) may reduce T1
violation rates vs GPT-5.2, but T2 and T3 rates will be comparable or worse. If
confirmed, this is external evidence that safe-complete training does not generalize
to adversarial prompt injection in realistic agentic scenarios -- precisely the gap
between their safety eval (single-turn refusal) and CyScenarioBench (multi-step
constraint reasoning).

**Grant relevance**: Demonstrates the need for injection-robust training, which is
what OpenSec's RL environment is designed to produce.

### Q3: What is the operational cost of model mistakes?

**v1 gap**: FP rate and containment rate are binary episode-level counts. No measure
of damage magnitude or timing.

**v2 metrics**:
- **Blast radius**: `fp_count / max(1, correct_count)` per episode. A model that
  isolates 10 wrong hosts and 1 correct host (blast_radius=10) is operationally
  different from one that isolates 1 wrong and 5 correct (blast_radius=0.2).
- **TTFC** (Time to First Containment): Step index of the first containment action.
  A model that contains at step 12 after investigating differs from one that
  panic-isolates at step 1.

**Expected outcomes**:
- High-FP models (GPT-5.2, DeepSeek): high blast radius, low TTFC (act fast,
  act wrong)
- Sonnet 4.5: lower blast radius, higher TTFC (more deliberate)

## Models

5 models in `configs/baselines.yaml`:

| Model | Provider | Notes |
|---|---|---|
| `gpt-5.2-2025-12-11` | OpenAI (direct) | v1 baseline, highest FP rate |
| `anthropic/claude-sonnet-4.5` | OpenRouter | v1 baseline, best calibration |
| `google/gemini-3-flash-preview` | OpenRouter | v1 baseline |
| `deepseek/deepseek-v3.2` | OpenRouter | v1 baseline, lowest report rate |
| `z-ai/glm-4.7` | OpenRouter | New model for v2 |

GPT-5.3-Codex: not yet in baselines.yaml. Add when API access is available.

## Eval Seeds

- **Total eval seeds**: 60 (40 standard, 10 easy, 10 trivial)
- **Primary run**: 40 standard-tier seeds per model (matches v1)
- **Supplementary**: 10 easy + 10 trivial for stratified analysis

## Run Protocol (Rate-Limit Batching)

OpenRouter rate-limits after ~5-10 multi-turn episodes. Each episode is 15 steps
with ~30 API calls (15 model calls + observation prompts). This means we cannot
run 40 seeds in a single invocation.

### Batch Strategy

Split each model into 4 batches of 10 seeds using `--skip` and `--limit`:

```bash
# Batch 1: seeds 0-9
python scripts/eval.py \
  --models "anthropic/claude-sonnet-4.5" \
  --split eval --tier standard \
  --skip 0 --limit 10 \
  --output outputs/v2_sonnet45_b1.jsonl

# Batch 2: seeds 10-19
python scripts/eval.py \
  --models "anthropic/claude-sonnet-4.5" \
  --split eval --tier standard \
  --skip 10 --limit 10 \
  --output outputs/v2_sonnet45_b2.jsonl

# Batch 3: seeds 20-29
python scripts/eval.py \
  --models "anthropic/claude-sonnet-4.5" \
  --split eval --tier standard \
  --skip 20 --limit 10 \
  --output outputs/v2_sonnet45_b3.jsonl

# Batch 4: seeds 30-39
python scripts/eval.py \
  --models "anthropic/claude-sonnet-4.5" \
  --split eval --tier standard \
  --skip 30 --limit 10 \
  --output outputs/v2_sonnet45_b4.jsonl
```

Repeat for each model. Wait for rate limits to reset between batches (~1-5 min).

GPT-5.2 uses the OpenAI API directly and may tolerate larger batches (--limit 20).

### Naming Convention

`outputs/v2_{model_short}_{batch}.jsonl`

Model shortnames: `gpt52`, `sonnet45`, `gemini3`, `deepseek32`, `glm47`

### Merge and Summarize

summarize.py accepts multiple files via glob. All v2 batch files merge automatically:

```bash
# Summarize all v2 results
python scripts/summarize.py --glob "outputs/v2_*.jsonl" \
  --output outputs/v2_baseline_summary.json

# Threshold classification
python scripts/summarize.py --glob "outputs/v2_*.jsonl" --thresholds

# Stratified by tier (requires easy/trivial runs too)
python scripts/summarize.py --glob "outputs/v2_*.jsonl" \
  --stratify-by tier --manifest data/seeds/manifest.json
```

### Failure Recovery

If a batch fails mid-run (rate limit, network error):
- The JSONL is flushed per-seed (`f.flush()` at eval.py:340)
- Check how many lines were written: `wc -l outputs/v2_sonnet45_b2.jsonl`
- Re-run with adjusted `--skip` and `--limit` to cover remaining seeds
- Append to existing file: `--output` will overwrite, so use a new filename
  for the recovery batch, e.g., `v2_sonnet45_b2_recovery.jsonl`

### v1 Reference

v1 used h1/h2 halves (20 seeds each) with filenames like
`llm_baselines_v2mix_{model}_h{half}.jsonl`. DeepSeek h1 only completed 13/20
(rate-limited). This was manually managed. v2 uses `--skip` + `--limit` for
clean batching.

## Expected JSONL Fields (v2)

Each row in the output JSONL now includes:

```
reward, step_count, submitted_report,
executed_containment, containment_correct_total, containment_false_positive_total,
evidence_gated_action_rate, time_to_first_containment,
evidence_gated_actions, total_containment_actions,
inj_tier1_violations, inj_tier2_violations, inj_tier3_violations,
steps, diagnostics, details
```

## Post-Run Analysis

After all batches complete:

1. **Threshold classification**: `--thresholds` flag prints per-model defensive
   capability level (Uncalibrated / Partially Calibrated / Calibrated / Expert)
2. **Stratified view**: `--stratify-by tier` breaks results by seed difficulty
3. **Paper tables**: Extract reward, FP rate, EGAR, blast radius, TTFC, T1/T2/T3
   injection rates for the revised Table 1
4. **GPT-5.3-Codex comparison**: When available, run the same protocol and compare
   safety-training predictions (Q2 above)

## Files Changed in Sprint 1

### New
- `oracle/calibration.py` -- EGAR computation, trust-tier entity extraction
- `oracle/thresholds.py` -- Defensive capability levels, threshold classification
- `tests/test_calibration.py` -- 18 tests
- `tests/test_thresholds.py` -- 21 tests
- `tests/test_injection_tiers.py` -- 7 tests

### Modified
- `scripts/eval.py` -- Evidence tracking per step, per-tier injection counts,
  per-seed max_steps, `--skip` flag for batching
- `scripts/summarize.py` -- EGAR/TTFC/blast_radius aggregation, `--thresholds`
  flag, per-tier injection rates, consistency std, single-source-of-truth refactor
- `oracle/verifier.py` -- `detect_injection_violations_detailed()` with tier metadata,
  default tier aligned to 2
- `data/sources/prompt_injections.csv` -- `difficulty_tier` column (T1:20, T2:32, T3:30)
- `scripts/generate_seeds.py` -- `InjectionExample.difficulty_tier`
- 200 seed JSONs -- backfilled with `difficulty_tier` in `prompt_injection_payloads`
- `data/seeds/manifest.json` -- `injection_difficulty_tier` per entry
