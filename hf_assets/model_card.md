---
license: apache-2.0
base_model: Qwen/Qwen3-4B-Instruct-2507
tags:
  - incident-response
  - cybersecurity
  - reinforcement-learning
  - gdpo
  - security-automation
  - agent
  - calibration
  - ai-safety
datasets:
  - Jarrodbarnes/opensec-seeds
language:
  - en
library_name: transformers
pipeline_tag: text-generation
---

# OpenSec-GDPO-4B

[![arXiv](https://img.shields.io/badge/arXiv-2601.21083-b31b1b.svg)](https://arxiv.org/abs/2601.21083)
[![GitHub](https://img.shields.io/badge/GitHub-opensec--env-blue)](https://github.com/jbarnes850/opensec-env)
[![Dataset](https://img.shields.io/badge/HF-Dataset-green)](https://huggingface.co/datasets/Jarrodbarnes/opensec-seeds)

A 4B parameter language model trained with **GDPO (Group Decomposed Policy Optimization)** for incident response agent calibration research. This is a **research checkpoint** demonstrating preliminary RL training on the OpenSec dual-control environment.

**Paper**: [OpenSec: Measuring Incident Response Agent Calibration Under Adversarial Evidence](https://arxiv.org/abs/2601.21083)

> **Status**: Research checkpoint. This model demonstrates modified but not improved calibration compared to frontier models. See [Limitations](#limitations) for deployment considerations.

## Architecture

<img src="opensec-design.jpeg" alt="OpenSec Architecture" width="100%"/>

*Figure: OpenSec dual-control architecture. The defender observes logs, alerts, and emails while the attacker advances through a state-constrained kill chain. Scoring is execution-based: containment actions are evaluated against ground truth, not report text.*

## Model Details

| Property | Value |
|----------|-------|
| **Base Model** | [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) |
| **Parameters** | 4B |
| **Training Method** | GDPO (Group Decomposed Policy Optimization) |
| **Training Data** | 160 taxonomy-stratified scenarios from [opensec-seeds](https://huggingface.co/datasets/Jarrodbarnes/opensec-seeds) |
| **Hardware** | Single NVIDIA A100 |
| **Rollout Engine** | SGLang |
| **License** | Apache 2.0 |

## Motivation

Frontier LLMs achieve high capability scores on security benchmarks but exhibit poor calibration in dual-control settings. When given authority to execute containment actions:

- **GPT-5.2, Gemini 3, DeepSeek**: 100% containment rate with 90-97% false positive rates
- **Sonnet 4.5**: 85% containment, 72% FP (partial calibration)

This checkpoint investigates whether calibration is trainable via reinforcement learning with decomposed reward functions.

## Training Method: GDPO

**Group Decomposed Policy Optimization** decouples normalization across reward components before aggregation, addressing reward-advantage collapse in multi-reward settings.

### Decomposed Reward Functions

| Component | Reward | Penalty | Purpose |
|-----------|--------|---------|---------|
| **Attribution** | +1 per correct field (5 max) | -0.5 per unknown | Correct incident identification |
| **Containment** | +1 per correct action | -0.5 per FP (capped at -1.0/category) | Precise threat response |
| **Injection Safety** | - | -2.0 per violation after exposure | Adversarial robustness |
| **Efficiency** | - | -0.1 per step | Operational speed |

### Training Configuration

```yaml
base_model: Qwen/Qwen3-4B-Instruct-2507
training:
  algorithm: GDPO
  epochs: 6
  precision: bf16
  rollout_engine: sglang
hardware:
  gpu: NVIDIA A100
  provider: Prime Intellect
```

## Evaluation Results

### Model Performance

| Metric | Value | Sonnet 4.5 (Reference) |
|--------|-------|------------------------|
| Containment executed | 0.75 | 0.85 |
| False positive rate | 0.70 | 0.72 |
| Correct containment | 0.475 | 0.85 |
| Injection violation | 0.375 | 0.40 |
| Report submitted | 0.25 | - |

### Comparison with Frontier Models

| Model | Cont. | FP | Correct | Injection |
|-------|------:|---:|--------:|----------:|
| GPT-5.2 | 1.00 | 0.97 | 0.97 | 0.38 |
| Sonnet 4.5 | 0.85 | 0.72 | 0.85 | 0.40 |
| Gemini 3 | 1.00 | 0.97 | 1.00 | 0.50 |
| DeepSeek 3.2 | 1.00 | 0.90 | 1.00 | 0.78 |
| **OpenSec-GDPO-4B** | **0.75** | **0.70** | **0.475** | **0.375** |

### Interpretation

The trained model shows **modified but not clearly improved** calibration:

- **Reduced containment rate** (75% vs 100% for most frontier models) suggests the model learned to act less frequently
- **Correct containment** (47.5%) is significantly lower than Sonnet 4.5 (85%), indicating the model did not learn to act more accurately
- **Report submission** (25%) dropped substantially, suggesting reward shaping issues

**Conclusion**: Direct RL from multi-component rewards is insufficient for achieving operational calibration. Future work should explore SFT warmup on successful trajectories and curriculum staging.

## Intended Use

### Research Applications

- **Calibration research**: Baseline for investigating action-execution calibration in security domains
- **RL methodology**: Reference checkpoint for GDPO and multi-objective reward decomposition
- **Curriculum learning**: Starting point for trivial-easy-standard progression experiments
- **Safety research**: Studying injection robustness under adversarial evidence

### Out-of-Scope Use

- **Production deployment**: This checkpoint is not calibrated for operational SOC use
- **Autonomous IR**: High false positive rates make unsupervised deployment unsafe
- **Security-critical applications**: Not suitable where incorrect containment has real consequences

## Limitations

### Training Limitations

1. **Low correct containment** (47.5%) compared to Sonnet 4.5 baseline (85%)
2. **Report submission collapse** (25%) indicates reward shaping issues
3. **Model learned to act less frequently but not more accurately**

### Recommended Improvements

Based on these results, improvements likely require:

1. **SFT warmup**: Pre-training on successful trajectory demonstrations before RL
2. **Curriculum staging**: Progressive difficulty using trivial/easy/standard tier seeds
3. **Explicit verification gates**: Reward structures that require evidence gathering before containment

### Security Considerations

This model processes simulated adversarial content (prompt injections) during training and should not be exposed to real attacker-controlled inputs without additional safeguards.

## Usage

### Loading the Model

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained(
    "Jarrodbarnes/opensec-gdpo-4b",
    torch_dtype="auto",
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained("Jarrodbarnes/opensec-gdpo-4b")
```

### Use with OpenSec Environment

```python
from datasets import load_dataset
from opensec import OpenSecEnvClient
import json
import tempfile

# Load evaluation scenario
ds = load_dataset("Jarrodbarnes/opensec-seeds", split="eval")
scenario = ds[0]

# Create seed file
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(scenario["seed"], f)
    seed_path = f.name

# Run episode
client = OpenSecEnvClient(base_url="http://localhost:8000")
obs = client.reset(seed_path=seed_path)

# Agent loop with model
while not obs["done"]:
    # Generate action with model
    prompt = format_observation(obs)
    action = model.generate(prompt)
    obs = client.step(action)
```

## Citation

```bibtex
@article{barnes2026opensec,
  title={OpenSec: Measuring Incident Response Agent Calibration Under Adversarial Evidence},
  author={Barnes, Jarrod},
  journal={arXiv preprint arXiv:2601.21083},
  year={2026}
}
```

## Related Resources

| Resource | Link |
|----------|------|
| Paper | [arXiv:2601.21083](https://arxiv.org/abs/2601.21083) |
| Code | [github.com/jbarnes850/opensec-env](https://github.com/jbarnes850/opensec-env) |
| Dataset | [Jarrodbarnes/opensec-seeds](https://huggingface.co/datasets/Jarrodbarnes/opensec-seeds) |
| Demo | [HuggingFace Space](https://huggingface.co/spaces/jarrodbarnes/opensec-env) |

## Contact

- **Author**: Jarrod Barnes
- **Email**: jarrod@arc.computer
- **Organization**: Arc Intelligence
