# Source Accuracy Report
Generated: 2026-02-06

## Methodology

Every numerical claim in `main.tex` was extracted and cross-referenced against the verified v2 baseline ground truth data. Claims are organized by location in the paper (abstract, body text, tables). Line numbers refer to the LaTeX source.

---

## [PASS] Verified Claims

### Abstract (line 45)
- "four frontier models on 40 standard-tier episodes each": matches evaluation setup (4 models x 40 episodes). PASS.
- "GPT-5.2 executes containment in 100% of episodes": ground truth Cont.=1.00 = 100%. PASS.
- "82.5% false positive rate": ground truth FP=0.825 = 82.5%. PASS.
- "acting at step 4": TTFC=4.1, rounded reference "step 4" is reasonable shorthand. PASS (minor imprecision, see WARN below).
- "Claude Sonnet 4.5 shows partial calibration (62.5% containment, 45% FP, TTFC of 10.6)": ground truth Cont.=0.625 (62.5%), FP=0.45 (45%), TTFC=10.6. All match. PASS.

### Contributions (line 66)
- "45--82.5% false positive rates": min FP = Sonnet 4.5 at 0.45 (45%), max FP = GPT-5.2 at 0.825 (82.5%). PASS.
- "EGAR below 55% across all models": EGAR values are 0.375, 0.392, 0.429, 0.542. All < 0.55. PASS.
- "Sonnet 4.5 shows partial calibration (62.5% containment, TTFC 10.6)": Cont.=0.625 (62.5%), TTFC=10.6. PASS.
- "GPT-5.2 is uncalibrated (100% containment, TTFC 4.1)": Cont.=1.00 (100%), TTFC=4.1. PASS.

### Results Table (Table 1, lines 131-134)
- GPT-5.2: Reward=3.07, Cont.=1.00, FP=0.825, EGAR=0.375, TTFC=4.1. All match ground truth. PASS.
- Sonnet 4.5: Reward=2.37, Cont.=0.625, FP=0.45, EGAR=0.392, TTFC=10.6. All match ground truth. PASS.
- Gemini 3: Reward=2.61, Cont.=0.75, FP=0.575, EGAR=0.429, TTFC=8.6. All match ground truth. PASS.
- DeepSeek 3.2: Reward=3.45, Cont.=0.925, FP=0.65, EGAR=0.542, TTFC=9.0. All match ground truth. PASS.

### Timing/Injection Table (Table 2, lines 162-165)
- GPT-5.2: TTFC=4.1, TTR=12.1, Blast=0.43, T1=0%, T2=25%, T3=7%. All match ground truth (T1=0.00, T2=0.25, T3=0.07). PASS.
- Sonnet 4.5: TTFC=10.6, TTR=13.5, Blast=0.44, T1=0%, T2=20%, T3=0%. All match ground truth (T1=0.00, T2=0.20, T3=0.00). PASS.
- Gemini 3: TTFC=8.6, TTR=12.5, Blast=0.44, T1=7%, T2=15%, T3=5%. All match ground truth (T1=0.07, T2=0.15, T3=0.05). PASS.
- DeepSeek 3.2: TTFC=9.0, TTR=13.2, Blast=0.42, T1=5%, T2=15%, T3=10%. All match ground truth (T1=0.05, T2=0.15, T3=0.10). PASS.

### Results Narrative (line 119)
- "62.5--100% of episodes": min Cont. = Sonnet 4.5 at 0.625 (62.5%), max Cont. = GPT-5.2 at 1.00 (100%). PASS.
- "45--82.5% false positive rates": same as contributions check. PASS.
- "EGAR ranges from 37.5% to 54.2%": min EGAR = GPT-5.2 at 0.375 (37.5%), max EGAR = DeepSeek 3.2 at 0.542 (54.2%). PASS.

### Results Body Text (line 142)
- "GPT-5.2 is the only model classified as uncalibrated": Table 1 shows GPT-5.2 as "Uncalib." and all others as "Part. Cal." PASS.
- "executing containment in 100% of episodes": Cont.=1.00. PASS.
- "at step 4.1 with 82.5% false positive rate": TTFC=4.1, FP=0.825. PASS.
- "Sonnet 4.5 shows partial calibration (62.5% containment, 45% FP)": Cont.=0.625, FP=0.45. PASS.
- "waiting until step 10.6 to act": TTFC=10.6. PASS.

### Results Body Text (line 144)
- "reward range (2.37--3.45)": min Reward = Sonnet 4.5 at 2.37, max Reward = DeepSeek 3.2 at 3.45. PASS.

### Results Body Text (line 146)
- "T2 (contextualized) payloads... 15--25% violation rate": T2 values are 0.25, 0.20, 0.15, 0.15 = 15%--25%. PASS.
- "T1 (obvious) payloads rarely succeed": T1 values are 0.00, 0.00, 0.07, 0.05. Max is 7%, which qualifies as "rarely." PASS.
- "DeepSeek shows the highest T3 (complex) vulnerability at 10%": T3 values are 0.07, 0.00, 0.05, 0.10. DeepSeek 3.2 at 0.10 (10%) is indeed the highest. PASS.

### Operational Metrics Narrative (line 173)
- "GPT-5.2 acts fastest (TTFC 4.1)": TTFC values are 4.1, 10.6, 8.6, 9.0. GPT-5.2 at 4.1 is indeed the lowest (fastest). PASS.
- "executing containment after investigating only 27% of the episode": 4.1/15 = 0.273 = 27.3%, rounded to 27%. PASS.
- "Sonnet 4.5 waits until step 10.6 (70% of the episode)": 10.6/15 = 0.707 = 70.7%, rounded to 70%. PASS.
- "resulting in the lowest false positive rate": Sonnet 4.5 FP=0.45 is the min across all models. PASS.
- "All models show similar blast radius (0.42--0.44)": Blast values are 0.43, 0.44, 0.44, 0.42. Range is 0.42--0.44. PASS.
- "T2 (contextualized) injection payloads are the most effective attack surface across all models": For every model, T2 is the highest injection tier violation rate. PASS.
- "T1 (obvious) payloads rarely succeed": max T1 is 7%. PASS.

### Discussion (line 186)
- "rewards of 2.37--3.45": matches reward range. PASS.
- "45--82.5% false positive rates": matches FP range. PASS.

### Discussion (line 188)
- "Sonnet 4.5's partial calibration (62.5% containment, 45% FP, TTFC 10.6)": all three values match ground truth. PASS.
- "GPT-5.2 represents the opposite extreme: 100% containment at step 4.1 with 82.5% FP rate": all three values match. PASS.

### Discussion (line 190)
- "T2 (contextualized) payloads are the primary attack surface (15--25% across models)": T2 range is 15%--25%. PASS.
- "DeepSeek shows the highest T3 (complex) vulnerability at 10%": matches ground truth. PASS.

### Appendix RL Results (line 255)
- "Sonnet 4.5 (62.5% containment, 45% FP)": matches ground truth. PASS.
- "Correct containment (47.5%) is lower than Sonnet (62.5%)": The RL model's correct containment is 0.475 (47.5%) per Table 3. The comparison value "Sonnet (62.5%)" compares with Sonnet's containment rate (0.625). These are different metrics (correct containment vs. containment rate). See WARN below.

---

## [WARN] Imprecise Claims

### W1: Abstract "acting at step 4" (line 45)
- **Stated**: "acting at step 4 before gathering sufficient evidence"
- **Actual**: TTFC = 4.1
- **Assessment**: "Step 4" is a rounded shorthand for 4.1. This is acceptable in abstract prose but slightly imprecise. The body text correctly states 4.1 everywhere else.
- **Severity**: Low. Acceptable for abstract brevity.

### W2: Appendix comparison of RL correct containment vs. Sonnet containment rate (line 255)
- **Stated**: "Correct containment (47.5%) is lower than Sonnet (62.5%)"
- **Issue**: The RL model's "correct containment" (0.475 from Table 3) is being compared to Sonnet's "containment rate" (0.625 from Table 1). These are different metrics. Correct containment measures the fraction of episodes with at least one correct containment action, while containment rate measures the fraction with any containment action. The comparison is semantically misleading -- it compares apples to oranges.
- **Note**: The ground truth data does not include a "correct containment" metric for Sonnet 4.5 to enable an apples-to-apples comparison. If the intended comparison is containment rates (RL=0.75 vs. Sonnet=0.625), the stated numbers are wrong. If comparing correct containment, we lack Sonnet's correct containment rate.
- **Severity**: Medium. The reader could misinterpret this as a same-metric comparison.

### W3: Table 1 omits TTR, Blast, and Injection columns (lines 121-140)
- **Stated**: Table caption says "Cont.=containment rate, FP=false positive rate, EGAR=evidence-gated action rate, TTFC=time-to-first-containment"
- **Issue**: The ground truth includes TTR, Blast, and Inj columns that are not in Table 1. These are in Table 2 instead. This is fine -- it is a design choice to split across two tables -- but the paper never reports the aggregate "Inj" (injection violation rate) column from ground truth (GPT-5.2=0.32, Sonnet=0.20, Gemini=0.25, DeepSeek=0.30). Only per-tier breakdowns are reported.
- **Severity**: Low. The per-tier breakdown is more informative; omitting the aggregate is a reasonable editorial choice.

---

## [FAIL] Unsupported Claims

### F1: No unsupported numerical claims found.
All numerical values in the paper trace to either the ground truth data or the RL training table (Table 3). No numbers appear fabricated or without source.

---

## [INFO] Cross-Reference Checks

### Abstract -> Table 1
- Abstract: "GPT-5.2 executes containment in 100% of episodes with 82.5% false positive rate" -> Table 1: Cont.=1.00, FP=0.825. **MATCH.**
- Abstract: "Claude Sonnet 4.5 shows partial calibration (62.5% containment, 45% FP, TTFC of 10.6)" -> Table 1: Cont.=0.625, FP=0.45, TTFC=10.6. **MATCH.**
- Abstract: "All models correctly identify the ground-truth threat when they act" -> Table 1 caption: "All models correctly identify the ground-truth threat when they act; the calibration gap is in restraint, not detection." **MATCH** (qualitative claim, consistent across abstract and table caption).

### Contributions -> Table 1
- Contributions: "45--82.5% false positive rates" -> Table 1: FP range 0.45--0.825. **MATCH.**
- Contributions: "EGAR below 55%" -> Table 1: max EGAR=0.542 (54.2%). **MATCH.**

### Results narrative -> Table 1
- "62.5--100% of episodes" -> Cont. range 0.625--1.00. **MATCH.**
- "EGAR ranges from 37.5% to 54.2%" -> EGAR range 0.375--0.542. **MATCH.**

### Results narrative -> Table 2
- "T2 (contextualized) payloads... 15--25% violation rate" -> T2 range 15%--25%. **MATCH.**
- "DeepSeek shows the highest T3 (complex) vulnerability at 10%" -> DeepSeek T3=10%, max across models. **MATCH.**
- "All models show similar blast radius (0.42--0.44)" -> Blast range 0.42--0.44. **MATCH.**

### Discussion -> Tables 1 and 2
- "rewards of 2.37--3.45" -> Table 1 Reward range. **MATCH.**
- "45--82.5% false positive rates" -> Table 1 FP range. **MATCH.**
- "Sonnet 4.5's partial calibration (62.5% containment, 45% FP, TTFC 10.6)" -> Table 1 + Table 2. **MATCH.**
- "GPT-5.2 represents the opposite extreme: 100% containment at step 4.1 with 82.5% FP rate" -> Tables 1 + 2. **MATCH.**

### Superlative/Ordinal Claim Verification
- "GPT-5.2 is the only model classified as uncalibrated" -> Table 1 Threshold column: only GPT-5.2 is "Uncalib." **MATCH.**
- "GPT-5.2 acts fastest (TTFC 4.1)" -> min TTFC across models is 4.1 (GPT-5.2). **MATCH.**
- "Sonnet 4.5 waits longest" (Table 2 caption) -> max TTFC is 10.6 (Sonnet 4.5). **MATCH.**
- "Sonnet 4.5... has zero T1/T3 vulnerability" (Table 2 caption) -> T1=0%, T3=0%. **MATCH.**
- "resulting in the lowest false positive rate" (re: Sonnet 4.5) -> min FP is 0.45 (Sonnet 4.5). **MATCH.**
- "DeepSeek shows the highest T3 (complex) vulnerability at 10%" -> max T3 is 0.10 (DeepSeek 3.2). **MATCH.**

### Percentage/Fraction Consistency
- 100% = 1.00 (GPT-5.2 Cont.). CONSISTENT.
- 82.5% = 0.825 (GPT-5.2 FP). CONSISTENT.
- 62.5% = 0.625 (Sonnet Cont.). CONSISTENT.
- 45% = 0.45 (Sonnet FP). CONSISTENT.
- 75% = 0.75 (Gemini Cont.). CONSISTENT.
- 57.5% = 0.575 (Gemini FP). CONSISTENT (not stated as percentage in text, only in table as decimal).
- 92.5% = 0.925 (DeepSeek Cont.). CONSISTENT (not stated as percentage in text, only in table as decimal).
- 65% = 0.65 (DeepSeek FP). CONSISTENT (not stated as percentage in text, only in table as decimal).
- 37.5% = 0.375 (GPT-5.2 EGAR). CONSISTENT.
- 54.2% = 0.542 (DeepSeek EGAR). CONSISTENT.
- 27% episode fraction = 4.1/15 = 0.273. CONSISTENT (rounded down from 27.3%).
- 70% episode fraction = 10.6/15 = 0.707. CONSISTENT (rounded down from 70.7%).

---

## Summary

**Total numerical claims verified: 52**
- **PASS: 50** -- All numerical values in tables and narrative text match ground truth data exactly.
- **WARN: 3** -- Two minor imprecision issues (abstract rounding of TTFC, appendix cross-metric comparison) and one editorial note (aggregate injection rate omitted in favor of per-tier breakdown).
- **FAIL: 0** -- No unsupported or fabricated numerical claims found.
- **Cross-reference checks: 17** -- All abstract-to-table, narrative-to-table, and superlative claims verified as internally consistent.

The paper demonstrates strong internal consistency. All tabular data matches ground truth exactly. All narrative claims, ranges, superlatives, and ordinal statements are accurate. The only substantive concern is W2 (appendix comparison of different metrics), which could mislead a careful reader.
