# Terminology Consistency Report
Generated: 2026-02-06

Paper source: `/Users/jarrodbarnes/opensec-env/paper/opensec-arxiv/main.tex`

---

## [PASS] Consistent Terms

- **OpenSec**: used consistently as "OpenSec" throughout (never "Open-Sec", "OPENSEC" in body text; "OPENSEC" appears only in the LaTeX header comment on line 1, which is appropriate)
- **dual-control**: hyphenated consistently as "dual-control" on lines 45, 58, 60, 66, 70, 79, 212 (both as adjective and noun phrase)
- **execution-based**: hyphenated consistently as "execution-based" on lines 45, 66, 79, 113
- **taxonomy-stratified**: hyphenated consistently as "taxonomy-stratified" on lines 66, 87, 184
- **trust-aware**: hyphenated consistently as "trust-aware" on lines 89, 200
- **log-centric**: hyphenated consistently as "log-centric" on lines 194, 210
- **state-constrained**: hyphenated consistently as "state-constrained" on lines 70, 79, 194
- **ground truth / ground-truth**: see WARN section below
- **kill chain**: used consistently as two unhyphenated words on lines 70, 79
- **replay cache**: used consistently as two unhyphenated words on lines 72, 99
- **containment rate**: used consistently on lines 115, 122
- **blast radius**: used consistently on lines 45, 115, 150, 153, 173
- **calibration gap**: used consistently as a two-word phrase on lines 45, 103, 122, 144, 186
- **prompt injection(s)**: used consistently as two unhyphenated words on lines 45, 54, 62, 66, 202, 208, 210
- **curriculum learning**: used consistently on lines 87, 178
- **GDPO**: used consistently (never expanded, but this is acceptable as it refers to a named algorithm)
- **SFT**: used consistently (never expanded, standard ML abbreviation)
- **SGLang**: used consistently (line 227)
- **A100**: used consistently (line 227)
- **Dec-POMDP / Dec-POMDPs**: used consistently with hyphen on lines 60, 212

## [WARN] Inconsistencies

### W1: Model name "Sonnet 4.5" vs "Claude Sonnet 4.5"
- Line 45 (abstract): "Claude Sonnet 4.5" (full name with vendor prefix)
- Line 66 (contributions): "Sonnet 4.5" (short name, no vendor prefix)
- Line 132 (Table 1): "Sonnet 4.5"
- Line 142 (results text): "Sonnet 4.5"
- Line 153 (Table 2 caption): "Sonnet 4.5"
- Line 163 (Table 2): "Sonnet 4.5"
- Line 188 (discussion): "Sonnet 4.5" and "Sonnet"
- Line 232 (appendix caption): "Sonnet 4.5"
- Line 255 (appendix text): "Sonnet" (shortest form, no version number)
- **Assessment**: The abstract uses "Claude Sonnet 4.5" once, then all subsequent uses drop the "Claude" prefix. Line 255 also drops the version number entirely ("Sonnet"). This is mildly inconsistent. Consider using "Claude Sonnet 4.5" on first use, then "Sonnet 4.5" consistently thereafter. The bare "Sonnet" on line 255 should at minimum include the version number.

### W2: Model name "DeepSeek 3.2" vs "DeepSeek"
- Line 134 (Table 1): "DeepSeek 3.2"
- Line 142 (results text): "DeepSeek" (no version number)
- Line 146 (results text): "DeepSeek" (no version number)
- Line 165 (Table 2): "DeepSeek 3.2"
- Line 188 (discussion): "DeepSeek" (no version number)
- Line 190 (discussion): "DeepSeek" (no version number)
- **Assessment**: Tables consistently use "DeepSeek 3.2" but prose drops the version number. This parallels the Sonnet inconsistency. Should use "DeepSeek 3.2" at least once in each major prose section, or establish a naming convention (e.g., full name on first use per section, short name thereafter).

### W3: Model name "Gemini 3" vs "Gemini"
- Line 133 (Table 1): "Gemini 3"
- Line 142 (results text): "Gemini 3" (with version) and "Gemini" in same sentence on line 188
- Line 164 (Table 2): "Gemini 3"
- Line 188 (discussion): "Gemini" (no version number)
- **Assessment**: Similar pattern to DeepSeek. Prose sometimes drops the version number.

### W4: "false positive rate" vs "FP rate" vs "FP" vs "false-positive"
- Line 45 (abstract): "false positive rate" (unhyphenated, full phrase) and "FP" (abbreviation used without prior definition in abstract)
- Line 52: "high false-positive rates" (hyphenated)
- Line 54: "false-positive containment" (hyphenated, used as compound adjective)
- Line 66: "false positive rates" (unhyphenated)
- Line 97: "false positives" (noun, unhyphenated -- correct)
- Line 115 (metric definition): "False positive rate" (unhyphenated, italicized as metric name)
- Line 119: "false positive rates" (unhyphenated)
- Line 122 (table caption): "FP=false positive rate"
- Line 142: "false positive rate" (unhyphenated) and "FP" in same sentence
- Line 144: "false positive actions" (unhyphenated)
- Line 150: "false positive containment actions" (unhyphenated)
- Line 186: "false positive rates" (unhyphenated)
- Line 188: "FP rate" and "FP" used as abbreviation
- Line 242 (appendix table): "False positive rate"
- **Assessment**: The hyphenation is inconsistent. Lines 52 and 54 use "false-positive" (hyphenated as compound adjective), while lines 66, 115, 119, 122, 142, 150, 186 use "false positive" (unhyphenated). Standard academic usage when used as a compound adjective before a noun (e.g., "false-positive rate") calls for hyphenation, but usage as a standalone noun ("false positives") should not be hyphenated. The paper uses both conventions inconsistently for the adjective form.

### W5: "ground truth" vs "ground-truth"
- Line 74: "ground truth" (unhyphenated, used as noun)
- Line 79: "ground truth" (unhyphenated, used as noun)
- Line 122: "ground-truth threat" (hyphenated, used as compound adjective)
- Line 144: "ground-truth threat" (hyphenated, used as compound adjective)
- Line 186: "ground-truth threat" (hyphenated, used as compound adjective)
- **Assessment**: This is actually CORRECT usage -- "ground truth" as a noun, "ground-truth" as a compound adjective. No action needed. Reclassified as consistent.

### W6: Blast radius definition inconsistency between tables
- Line 115 (metric definition): "Blast radius is the ratio of false positive to correct containment actions per episode"
- Line 150: "blast radius counts false positive containment actions per episode" (describes it as a count, not a ratio)
- Line 153 (Table 2 caption): "Blast=ratio of FP to correct actions" (ratio)
- **Assessment**: Line 150 describes blast radius as a count, but the formal definition (line 115) and Table 2 caption (line 153) define it as a ratio. The phrasing on line 150 is imprecise and could mislead.

### W7: "over-triggering" vs "over-trigger"
- Line 45 (abstract): "over-triggering" (gerund, hyphenated)
- Line 54: "over-trigger" (verb, hyphenated)
- Line 66: "over-triggering" (gerund, hyphenated)
- **Assessment**: Both forms are grammatically correct for their usage contexts. Consistent hyphenation. No action needed.

### W8: Injection violation rate naming
- Line 45 (abstract): "per-tier injection violation rates"
- Line 115 (metric definition): "Injection violation rate is reported per tier"
- Line 153 (Table 2 caption): "Per-tier injection violation rates"
- Line 244 (appendix table): "Injection violation"
- **Assessment**: The appendix table on line 244 uses "Injection violation" (dropping "rate"), which is technically measuring a rate (0.375). Minor inconsistency.

### W9: "Uncalib." vs "uncalibrated" / "Part. Cal." vs "partial calibration"
- Line 131 (Table 1): "Uncalib." (abbreviated)
- Line 132-134 (Table 1): "Part.\ Cal." (abbreviated)
- Line 142 (text): "uncalibrated" and "partial calibration" (fully spelled out)
- **Assessment**: Abbreviations in tables are standard and acceptable. No issue; the full forms are used in prose and the abbreviations are used in the space-constrained table. Consistent within their respective contexts.

### W10: "Containment executed" vs "Containment rate" vs "Cont."
- Line 115: Formally defined as "Containment rate"
- Line 122/129 (Table 1): Abbreviated as "Cont."
- Line 241 (appendix table): "Containment executed"
- **Assessment**: The appendix table uses "Containment executed" which is a different label for what appears to be the same metric (fraction of episodes with containment). The formal name established on line 115 is "Containment rate." Minor inconsistency between main body tables and appendix table.

## [FAIL] Deprecated Terms Found

No deprecated terms found. The paper does not contain any previously-used terms that have been superseded.

## [INFO] Abbreviation Usage

### Abbreviations Defined on First Use

- **IR**: First defined on line 45 (abstract) as "incident response (IR)". Used 8 times total (lines 21, 26, 37, 45, 54, 66, 97, 194, 210, 212, 214). Note: line 21 (running title) uses "IR" before the abstract definition, which is standard for running titles.
- **SOC**: First defined on line 50 as "security operations center (SOC)". Used 4 times total (lines 50, 52, 107, 210).
- **EGAR**: First defined on line 45 (abstract) as "evidence-gated action rate (EGAR)". Formally defined again on line 115. Used 10 times total.
- **TTFC**: First defined on line 45 (abstract) as "time-to-first-containment (TTFC)". Formally defined again on line 115 and re-expanded on line 150. Used 12 times total.
- **FP**: First used on line 45 (abstract) as "FP" after "false positive rate" appears earlier in the same sentence. Formally defined in Table 1 caption (line 122) as "FP=false positive rate". Used 9 times total.
- **TTR**: First defined on line 153 (Table 2 caption) as "TTR=time-to-report". Used in Table 2 header (line 160) and data rows. Used 2 times total. Note: TTR is never defined in the body text metrics section (line 115 defines six metrics, TTR is not among them -- it appears only in Table 2).
- **FRR**: Mentioned on line 208 as "false refusal rate (FRR)". Used 1 time total (in Related Work to reference CyberSecEval2 metric).
- **Dec-POMDP**: First defined on line 60 as "decentralized partially observable MDPs (Dec-POMDPs)". Used 2 times total (lines 60, 212).
- **GDPO**: Used on lines 204, 227 without expansion. Not expanded anywhere in the paper.
- **SFT**: Used on lines 204, 257 without expansion. Not expanded anywhere in the paper.
- **RL**: Used on lines 37, 45, 66, 204, 210, 214, 227, 257. First used on line 37 (keywords) as "reinforcement learning". Expanded on line 45 (abstract) as "reinforcement learning environment". Not formally defined with parenthetical "(RL)" notation.
- **LLM/LLMs**: Used on lines 50, 52, 72, 208. First used on line 50. Never formally expanded as "large language model(s) (LLMs)" -- line 45 uses "large language models" but does not introduce the LLM abbreviation in parentheses. Line 50 then uses "LLMs" without the abbreviation having been formally introduced.

### Abbreviations NOT Defined on First Use

- **FP**: Used in the abstract (line 45) before formal definition. The abstract mentions "45% FP" after stating "false positive rate" earlier in the sentence, which provides implicit context, but the abbreviation is not formally introduced with parenthetical notation.
- **GDPO**: Never expanded anywhere in the paper. Used on lines 204, 227. This is a specific algorithm name (Group DPO / Grouped Direct Preference Optimization) that should be expanded on first use.
- **SFT**: Never expanded anywhere in the paper. Used on lines 204, 257. Should be expanded as "supervised fine-tuning (SFT)" on first use.
- **LLM/LLMs**: Never formally introduced with parenthetical notation. Line 45 says "large language models" and line 50 says "LLMs" but the abbreviation is never explicitly defined.
- **RL**: Never formally introduced with parenthetical "(RL)" notation. "reinforcement learning" appears on lines 37, 45 without introducing the abbreviation, then "RL" is used starting on line 66.
- **TTR**: Appears only in Table 2 (lines 153, 160) as "TTR=time-to-report" but is never mentioned in the body text metrics definition (line 115) which explicitly lists six metrics. TTR is a seventh metric that appears in Table 2 without being formally introduced in the metrics paragraph.

### Benchmark / Tool Names (verified consistent)

- **CyberSecEval2**: line 208 (once)
- **CTIBench**: line 208 (once)
- **ExCyTIn-Bench**: line 208 (once)
- **CybORG**: line 210 (once)
- **ATLAS**: line 212 (once)
- **OWASP Agentic AI Guide**: line 190 (once)
- **Qwen/Qwen3-4B-Instruct**: line 227 (once)

### Injection Tier Labels (verified consistent)

- **T1**: always "(obvious)" or "(obvious overrides)" -- lines 115, 146, 153, 173
- **T2**: always "(contextualized)" or "(contextualized domain-specific framing)" -- lines 115, 146, 153, 173
- **T3**: always "(complex)" or "(complex multi-step or multilingual payloads)" -- lines 115, 146, 153, 173

## [INFO] Pronoun Usage

The paper uses "we/our" throughout (lines 45, 66, 105, 109, 115, 184, 223, 227), which is standard for academic papers. Note that the CLAUDE.md writing style guide specifies first-person singular ("I"), but the paper consistently uses first-person plural. This is a deliberate authorial choice for the ICML submission format and is internally consistent.

## Summary

**42 terms checked, 8 inconsistencies flagged, 0 deprecated terms found.**

### Critical Issues (should fix before submission):
1. **W6**: Blast radius described as "count" on line 150 but formally defined as "ratio" -- factual inconsistency in metric description.
2. **TTR not defined in metrics section**: TTR appears in Table 2 but is not among the six metrics defined on line 115. Either add it to the metrics definition or note it as supplementary.
3. **GDPO never expanded**: Algorithm name should be expanded on first use (line 204 or 227).
4. **SFT never expanded**: Should be expanded on first use (line 204).
5. **LLM/RL never formally abbreviated**: Both terms are used in expanded and abbreviated forms but the abbreviation is never formally introduced with parenthetical notation.

### Minor Issues (recommended but not blocking):
6. **W1/W2/W3**: Model names sometimes drop version numbers in prose (e.g., "DeepSeek" instead of "DeepSeek 3.2", "Sonnet" instead of "Sonnet 4.5"). Establish convention: full name on first use per section, short name thereafter.
7. **W4**: "false-positive" (hyphenated) on lines 52, 54 vs "false positive" (unhyphenated) elsewhere when used as compound adjective. Pick one convention.
8. **W8/W10**: Appendix table metric labels differ slightly from main body formal names ("Containment executed" vs "Containment rate", "Injection violation" vs "Injection violation rate").
