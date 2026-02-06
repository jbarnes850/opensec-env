# Verification Executive Summary
Generated: 2026-02-06
Paper: OpenSec: Calibrating Incident Response Agents Under Adversarial Evidence (arXiv:2601.21083)

## Critical Issues (must fix before submission)

1. **Figures not cross-referenced from text** (02_figures W1-W2): Neither Figure 1 (`fig:architecture`) nor Figure 2 (`fig:pipeline`) is referenced via `\ref{fig:...}` or hardcoded "Figure N" anywhere in the paper body. ICML reviewers expect in-text references to all figures. [Figures report]
2. **Blast radius described as "count" on line 150** (03_terminology W6, 05_source W2): Line 150 says "blast radius counts false positive containment actions per episode" but the formal definition (line 115) and Table 2 caption (line 153) define it as a ratio. Factual inconsistency. [Terminology report, Source accuracy report]
3. **GDPO never expanded** (03_terminology): Used on lines 204, 227 without expansion. Should be "Group Direct Preference Optimization (GDPO)" on first use. [Terminology report]
4. **SFT never expanded** (03_terminology): Used on lines 204, 257 without expansion. Should be "supervised fine-tuning (SFT)" on first use. [Terminology report]
5. **LLM never formally abbreviated** (03_terminology): "large language models" appears on line 45 but the abbreviation "LLMs" (line 50) is never introduced with parenthetical notation. [Terminology report]
6. **RL never formally abbreviated** (03_terminology): "reinforcement learning" appears on lines 37, 45 but "RL" abbreviation (first used line 66) is never introduced with parenthetical notation. [Terminology report]
7. **TTR not defined in metrics section** (03_terminology W8): TTR appears in Table 2 (lines 153, 160) but is not among the metrics defined in the metrics paragraph (line 115). [Terminology report]
8. **Appendix compares different metrics** (05_source W2): Line 255 compares RL "correct containment" (47.5%) to Sonnet "containment rate" (62.5%). These are different metrics -- misleading apples-to-oranges comparison. [Source accuracy report]

## Warnings (should fix)

9. **Model names inconsistent in prose** (03_terminology W1-W3): "DeepSeek" without version (lines 142, 146, 188, 190) vs "DeepSeek 3.2" in tables. Same for "Sonnet" (line 255) and "Gemini" (line 188). Recommend full name on first use per section, short name thereafter.
10. **"false-positive" hyphenation inconsistent** (03_terminology W4): Lines 52, 54 use "false-positive" (hyphenated as compound adjective), while lines 66, 115, 119, 142, 150, 186 use "false positive" (unhyphenated). Pick one convention for the adjective form.
11. **Appendix table metric labels differ from body** (03_terminology W10): "Containment executed" (line 241) vs formal name "Containment rate" (line 115). "Injection violation" (line 244) vs "Injection violation rate."
12. **Adjacent citations could be combined** (01_citations): Lines 50 and 214 have adjacent single-key `\citep` commands that could be combined into multi-key citations for compactness.
13. **CyberSecEval2 venue could be upgraded** (01_citations): Published at EMNLP 2024 but cited as @misc. Consider upgrading to @inproceedings.
14. **Float specifier warning** (04_formatting): Table 3 (appendix) uses `[h]` which LaTeX overrides to `[ht]`. Change to `[ht]` in source to suppress warning.
15. **Abstract rounds TTFC** (05_source W1): "acting at step 4" when actual TTFC is 4.1. Acceptable for abstract brevity but slightly imprecise.

## Status by Category

| Category | Pass | Warn | Fail |
|----------|------|------|------|
| Citations | 14 | 11 | 0 |
| Figures | 2 | 2 | 0 |
| Terminology | 42 terms | 8 | 0 |
| Formatting | 14 | 7 | 0 |
| Source Accuracy | 50 | 3 | 0 |

## Recommended Action Order

1. Add `Figure~\ref{fig:architecture}` and `Figure~\ref{fig:pipeline}` references in appropriate body text locations
2. Fix blast radius wording on line 150 ("ratio" not "count")
3. Add formal abbreviation introductions for LLM, RL, GDPO, SFT
4. Add TTR to metrics definition paragraph or note it as supplementary
5. Fix appendix cross-metric comparison (line 255)
6. Standardize "false positive" hyphenation (recommend unhyphenated for consistency with majority usage)
7. Standardize model name convention (full name on first use per section)
8. Fix appendix table metric labels to match formal names
9. Combine adjacent citations on lines 50 and 214
10. Change appendix table float specifier from `[h]` to `[ht]`
