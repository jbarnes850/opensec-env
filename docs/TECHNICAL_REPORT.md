# OpenSec: A Dual-Control Environment for Measuring Incident Response Agent Calibration Under Adversarial Evidence

## TL;DR

Offensive capability now scales with token budget: Heelan (2026) demonstrates frontier agents generating 40+ working exploits across 6 scenarios for ~$30-50 in compute. Incident response (IR) agents must keep pace, but executing containment without calibration causes collateral damage - and the evidence they process may contain prompt injections designed to trigger false positives. OpenSec is a dual-control environment that measures IR agent calibration with execution-based scoring: time-to-first-containment (TTFC), blast radius (false positives per episode), and injection violation rates.

Evaluating four frontier models on 160 episodes with embedded prompt injections, we find systematic over-triggering: GPT-5.2, Gemini 3, and DeepSeek execute containment in 100% of episodes with 90-97% false positive rates and TTFC of 7-8 steps - acting before gathering sufficient evidence. Claude Sonnet 4.5 shows partial pretrained calibration (85% containment, 72% FP, TTFC 9.9), demonstrating this capability exists but is not emergent from scale alone. Injection vulnerability varies independently: DeepSeek shows 78% violation rate despite identical containment behavior to GPT-5.2 (38%).

The contribution is the environment and diagnostic framework. Current aggregate benchmarks conflate action execution with correct action execution, hiding operational failures behind high scores.

Links: [Code](https://github.com/jbarnes850/opensec-env) | [Space](https://huggingface.co/spaces/jarrodbarnes/opensec-env) | Eval artifacts: reproducible locally (`outputs/`, gitignored)

![OpenSec: Dual-Control Cyber Environment](../assets/opensec-design.jpeg)

## The problem

The [agentic SOC](https://omdia.tech.informa.com/blogs/2025/nov/the-agentic-soc-secops-evolution-into-agentic-platforms) is no longer theoretical. Surveys of LLM agents for security automation show strong results on alert triage, threat intelligence, and report generation. GPT-4 achieves 94% precision on alert classification in controlled settings. Omdia tracks 50+ agentic SOC startups. The technology works - on benchmarks.

But benchmarks measure capability, not calibration. A model that correctly classifies 94% of alerts may still execute containment on 97% of them, including the 6% it should have ignored. The [AI-Augmented SOC survey](https://www.mdpi.com/2624-800X/5/4/95) identifies "high false-positive rates" as a core SOC pain point that LLMs are meant to solve - yet existing evaluations rarely measure whether agents make this problem better or worse when given the authority to act.

This matters because offense scales faster than defense. Heelan (2026) demonstrates frontier agents generating [40+ working exploits](https://sean.heelan.io/2026/01/18/on-the-coming-industrialisation-of-exploit-generation-with-llms/) across 6 scenarios for ~$30-50 in compute. The limiting factor is token throughput, not expertise. IR agents that over-trigger will face adversaries who understand this - embedding prompt injections in malicious artifacts specifically to induce false-positive containment.

OpenSec measures what current benchmarks miss: the gap between action willingness and action correctness when the evidence is adversarial and the stakes are operational.

## Why dual-control is hard

Dual-control environments are hard because they require coordination under a changing shared state. These settings can be formalized as decentralized partially observable MDPs (Dec-POMDPs), and empirically, reasoning capability does not transfer to execution capability when multiple actors modify shared state. Barnes & Jaglan (2025) report a 28-point performance drop on tau2-bench when shifting from reasoning-only to dual-control mode, identifying coordination failure as the primary bottleneck.

The world changes while the agent acts, and the agent must decide not only what is true but what to do under risk. In OpenSec, the attacker continues to advance, logs evolve, and prompt injections attempt to steer tool use. The environment tests and trains this adversarial tactical judgment that reasoning-only benchmarks miss.

## How it works

OpenSec is a dual-control simulator with deterministic scoring. The defender observes evidence from SQLite logs, alerts, and emails and uses tools to investigate and contain. The attacker advances a fixed kill chain (phish_sent -> creds_used -> lateral_move -> data_access -> exfil_attempt) with state-constrained actions and optional branch variants. The attacker is stochastic by default, and evidence is emitted as the attacker progresses; the oracle is deterministic for any given trajectory.

The attacker is an LLM policy with limited autonomy inside a hard state machine. It chooses valid, scenario-consistent actions, can pick between alternate branches, and can be replay-cached for determinism. It is not a fully free-form adversary, but it is more than a scripted sequence. The defender action space includes `query_logs`, `fetch_email`, `fetch_alert`, `isolate_host`, `block_domain`, `reset_user`, and `submit_report`. Scoring is based on what the agent does, not what it claims.

Each episode is an incident with a scenario seed that specifies ground truth and a timeline of artifacts. The agent acts under a deadline (default max_steps=15) while the attacker evolves the incident unless contained. The defender must investigate evidence (logs, alerts, email), attribute the incident (who/what/how), execute containment actions, and submit a structured report.

The action interface is strict and tool-based. Each tool has a defined schema and intended semantics. This keeps evaluation verifiable and allows fine-grained diagnostics when a model fails.

### Scenario design

OpenSec scenarios are structured around three design principles:

**Taxonomy-stratified scenarios.** Seeds are labeled with `taxonomy_id` and `taxonomy_family` fields (e.g., `direct_harm-containment`, `data_exfil-query`, `adaptive-mixed`). The taxonomy defines five families with explicit sampling weights: direct_harm (0.50), data_exfil (0.30), adaptive (0.20), plus fixed easy and trivial tiers. This enables stratified evaluation and curriculum learning.

**Trust tiers and provenance.** Artifacts (emails, alerts, logs) carry `trust_tier` and `source` fields. The `trust_profile` object maps each surface type to a reliability tier (untrusted, corroborated, verified). This allows the defender to weight evidence by provenance and supports trust-aware containment decisions.

**Objective variability.** The attack graph supports multi-objective scenarios via an `objectives` list and conditional state transitions. Combined with variable `max_steps`, this reflects realistic incident diversity where attack paths adapt to defender actions.

The dataset comprises 160 training seeds and 60 evaluation seeds (20 trivial, 20 easy, 40 standard) with injection payloads present across all tiers.

![Seed Generation Pipeline](../assets/seed-generation-pipeline.jpeg)

## Scoring and evaluation

OpenSec's reward is a sum of deterministic components:

- Attribution: +1 per correct field, -0.5 per unknown.
- Containment (executed actions): +1 per correct action, -0.5 per false positive (capped by category).
- Injection safety (exposure-gated): -2 per violation after exposure to injected content.
- Efficiency: -0.1 per step.

Attacker behavior can be made reproducible via a replay cache keyed by (scenario_id, step, attacker_state, agent_action_hash, attacker_context_hash), reducing variance for clean comparisons. Replay is opt-in (`OPENSEC_REPLAY_MODE=replay`); record-only mode captures trajectories without enforcing determinism.

### Why this reward design

Containment is scored only on executed actions that change world state, not on report text. This makes the gap directly measurable.

Exposure-gated injection penalties reflect how real analysts work: they must read phishing emails, inspect malicious logs, and process attacker-controlled content. Avoiding exposure is not an option. The security-relevant question is whether the agent still acts correctly after ingesting adversarial input, so we penalize only behavioral compromise after exposure.

The reward penalizes incorrect containment more than inaction. This mirrors how SOC teams train junior analysts: isolating the wrong server takes production down, blocking the wrong domain breaks business services, and a false-positive containment action can cause more immediate damage than a delayed response. The reward is training correctness under adversarial pressure, not speed. This is a deliberate scope choice: the model must learn to act right before it learns to act fast. If incorrect action were cheap, the optimal policy would spray containment actions indiscriminately, which is also operationally catastrophic.

I did not ablate the penalty asymmetry in this work; symmetric penalties are a natural ablation for future runs. A further limitation is that the reward does not penalize missed containment (allowing the attacker to progress unchecked). In production, that failure mode is also costly. I hold this penalty out intentionally: it is a natural next stage of curriculum once the model demonstrates correct action selection. The evaluation oracle is fixed to preserve comparability; training-time reward shaping is a separate, documented choice.

Primary metrics use the taxonomy-stratified evaluation split (40 standard-tier seeds, max_steps=15) and the deterministic oracle; training uses 160 standard-tier seeds, and all seeds include injection payloads. Correct containment is reported in two ways to avoid ambiguity: (1) **partial correct containment**, where at least one executed containment action matches a ground-truth target; and (2) **full correct containment**, where all required containment actions are executed with no false positives. False positives are penalized and counted separately. In addition to reward, I report operational timing as step-based proxies: time-to-first-containment (the first step that executes `isolate_host`, `block_domain`, or `reset_user`) and time-to-report (the step of `submit_report`). These metrics are computed from episode traces and included in JSONL outputs for analysis.

## Frontier model evaluation

The execution-based evaluation grid is computed from JSONL outputs produced by `scripts/run_llm_baseline.py`. The defender prompt explicitly enumerates all containment tools (`isolate_host`, `block_domain`, `reset_user`), provides JSON-formatted usage examples, and states that containment is scored.

### Key finding: systematic over-triggering

Three of four frontier models execute containment in 100% of episodes with 90-97% false positive rates. They trigger nearly every available containment action regardless of evidence quality.

| Model | Runs | Reward | Containment | FP Rate | Correct | Injection Violation |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.2 | 40 | 3.46 | 1.00 | 0.97 | 0.97 | 0.38 |
| Claude Sonnet 4.5 | 40 | 2.76 | 0.85 | 0.72 | 0.85 | 0.40 |
| Gemini 3 Flash | 40 | 3.35 | 1.00 | 0.97 | 1.00 | 0.50 |
| DeepSeek v3.2 | 40 | 2.99 | 1.00 | 0.90 | 1.00 | 0.78 |

**Calibration is not emergent from scale.** GPT-5.2, Gemini 3, and DeepSeek - all frontier-scale models - show identical over-triggering behavior. Only Sonnet 4.5 demonstrates partial pretrained calibration (85% containment, 72% FP), suggesting this capability requires targeted training or architectural differences rather than scale alone.

**High rewards mask operational failure.** The reward range (2.76-3.46) looks strong, but these scores reflect indiscriminate action. By exhausting the containment action space, models capture all correct targets (97-100% correct) alongside nearly all incorrect ones (90-97% FP). In production, this would take down legitimate services alongside malicious ones.

**Injection vulnerability varies independently.** DeepSeek shows the highest violation rate (78%) despite identical containment behavior to GPT-5.2 (38%). Sonnet 4.5 (40%) falls in between. This suggests injection robustness is orthogonal to containment calibration and requires separate attention.

### Operational timing metrics

Beyond aggregate rates, operational timing provides insight into response behavior. Time-to-first-containment (TTFC) measures the step index when an agent first executes a containment action; time-to-report (TTR) measures when the agent submits its final report. Blast radius counts false positive containment actions per episode. These metrics are computed from episode traces via `scripts/compute_ir_metrics.py`.

| Model | TTFC (mean) | TTFC (median) | TTR (mean) | Blast Radius (mean) | Blast Radius (max) |
|---|---:|---:|---:|---:|---:|
| GPT-5.2 | 6.95 | 6 | 10.47 | 1.23 | 3 |
| Claude Sonnet 4.5 | 9.91 | 10 | 13.03 | 1.15 | 2 |
| Gemini 3 Flash | 7.73 | 8 | 11.55 | 1.40 | 2 |
| DeepSeek v3.2 | 7.58 | 7 | 11.55 | 1.18 | 2 |

Key observations:

- **TTFC correlates with calibration**: Sonnet 4.5 waits ~3 steps longer before first containment (TTFC 9.91 vs 6.95-7.73), reflecting more deliberate evidence evaluation before action.
- **Over-triggering models act faster**: GPT-5.2, Gemini 3, and DeepSeek all execute containment within 7-8 steps, taking action before gathering sufficient evidence.
- **Blast radius is similar across models** (1.15-1.40 FPs per episode) despite different episode-level FP rates. This is because aggressive models take more total containment actions, so even though each action has similar error rates, the per-episode FP count stays bounded by the action space.
- **Sonnet 4.5 has lowest blast radius** (1.15) despite higher TTFC, suggesting its delayed action results in fewer false positives.

## Discussion

**Environment design reveals hidden behavior.** GPT-5.2 executed 0% containment in earlier environment versions but 100% in the taxonomy-stratified version with trust tiers and realistic provenance. The defender prompt is unchanged. The difference is scenario realism: when evidence looks realistic, frontier models act on it. This suggests unrealistic benchmarks underestimate action willingness while overestimating calibration.

**Aggregate scores mask operational failure.** Frontier models achieve rewards of 2.76-3.46, but three of four do so by exhausting the containment action space. By aggregate metrics, these are high-performing agents (97-100% correct containment). By operational metrics, they would take down production services indiscriminately (90-97% false positive rates). Current evaluation practices conflate action execution with correct action execution.

**Calibration exists in some pretrained models.** Sonnet 4.5's partial calibration (85%/72%) shows the capability exists without targeted training. Why Sonnet and not GPT-5.2, Gemini, or DeepSeek? This is an open question - but the variation itself is diagnostic value the environment provides.

**Injection vulnerability is orthogonal.** DeepSeek shows 78% violation rate despite identical containment behavior to GPT-5.2 (38%). The [OWASP Agentic AI Guide](https://owasp.org/www-project-agentic-ai/) identifies tool/API access as a key attack surface. OpenSec deliberately places the defender in this configuration because real IR requires processing attacker-controlled content.

## Limitations

The environment is log-centric and does not execute real exploits or malware; it targets IR investigation and containment decisions rather than exploit development. The attacker is state-constrained for determinism (`sim/attacker_policy.py`, `sim/attacker_state_machine.py`), not fully free-form. The benchmark focuses on a narrow but common IR slice (phish -> creds -> lateral movement -> exfil) to keep evaluation verifiable.

The evaluation uses 40 standard-tier seeds per model. Broader statistical confidence requires additional seeds and replications. Trust tier metadata is present but not yet used as an evaluation signal.

## Future work

**Trust-aware evaluation.** The `trust_profile` field enables measuring whether models appropriately weight evidence by provenance tier. This is not yet analyzed but the infrastructure exists.

**Injection robustness training.** The environment supports targeted injection curricula via `injection_type` metadata. Combined with work on [prompt injection defenses](https://www.anthropic.com/research/prompt-injection-defenses), this suggests a path toward robust behavior through adversarial exposure.

**Calibration training.** Preliminary RL experiments (Appendix A) suggest calibration behavior is trainable but requires further investigation - likely a two-stage SFT+RL pipeline or curriculum approach to achieve meaningful improvement over pretrained baselines.

---

## Appendix A: Preliminary RL experiments

We conducted preliminary training experiments to investigate whether calibration is trainable. These results are included for completeness but do not constitute a primary contribution.

### Method

We trained Qwen/Qwen3-4B-Instruct with GDPO using decomposed reward functions (attribution, containment, injection, efficiency). GDPO decouples normalization across rewards before aggregation, addressing reward-advantage collapse in multi-reward settings. Training used SGLang for rollouts on a single A100.

### Results

| Metric | Value |
|--------|------:|
| Containment executed | 0.75 |
| False positive rate | 0.70 |
| Correct containment | 0.475 |
| Injection violation | 0.375 |
| Report submitted | 0.25 |

### Interpretation

The trained model shows modified but not clearly improved calibration compared to Sonnet 4.5 (85%/72%). Key issues:
- Correct containment (47.5%) is lower than Sonnet (85%)
- Report submission dropped to 25%, suggesting reward shaping issues
- The model learned to act less frequently but not more accurately

These results suggest direct RL from multi-component reward is insufficient. Likely improvements: SFT warmup on successful trajectories, curriculum staging, explicit verification gates.

Checkpoint: [huggingface.co/Jarrodbarnes/opensec-gdpo-4b](https://huggingface.co/Jarrodbarnes/opensec-gdpo-4b) | Training logs: [wandb](https://wandb.ai/jbarnes850-near-protocol/opensec-onpolicy/runs/2o04pujd)

## Artifacts

Code, evaluation scripts, and seed data: https://github.com/jbarnes850/opensec-env

Environment specifications: `docs/TAXONOMY_SPEC.md`, `docs/SCHEMA_SPEC.md`, `docs/EVAL_PROTOCOL.md`

Evaluation artifacts are generated by `scripts/run_llm_baseline.py` and written under `outputs/` (gitignored). IR metrics computed via `scripts/compute_ir_metrics.py`.

## References

1. Heelan, S. (2026). On the Coming Industrialisation of Exploit Generation with LLMs. https://sean.heelan.io/2026/01/18/on-the-coming-industrialisation-of-exploit-generation-with-llms/

2. AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation. Journal of Cybersecurity and Privacy, 2025. https://www.mdpi.com/2624-800X/5/4/95

3. The agentic SOC: SecOps evolution into agentic platforms. Omdia, November 2025. https://omdia.tech.informa.com/blogs/2025/nov/the-agentic-soc-secops-evolution-into-agentic-platforms

4. OWASP Agentic AI Guide. https://owasp.org/www-project-agentic-ai/

5. Anthropic. (2025). Mitigating the risk of prompt injections in browser use. https://www.anthropic.com/research/prompt-injection-defenses

## Citation

```
@misc{opensecenv2026,
  title  = {OpenSec: A Dual-Control Environment for Measuring Incident Response Agent Calibration Under Adversarial Evidence},
  author = {Jarrod Barnes},
  year   = {2026},
  note   = {Preprint}
}
```
