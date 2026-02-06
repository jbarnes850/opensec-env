# Figure Verification Report
Generated: 2026-02-06

## [PASS] Verified Figures
- Figure 1: `figures/opensec-design.png` - file exists (2.19 MB), label `fig:architecture`, caption present (line 79): "OpenSec dual-control architecture..."
- Figure 2: `figures/seed-generation-pipeline.png` - file exists (1.81 MB), label `fig:pipeline`, caption present (line 178): "Seed generation pipeline with taxonomy stratification..."

## [WARN] Issues
- Figure 1 (`fig:architecture`): Label defined at line 80 but never referenced via `\ref{fig:architecture}` anywhere in the paper body. The figure is included but no in-text cross-reference points the reader to it.
- Figure 2 (`fig:pipeline`): Label defined at line 179 but never referenced via `\ref{fig:pipeline}` anywhere in the paper body. The figure is included but no in-text cross-reference points the reader to it.
- No hardcoded "Figure N" or "Fig. N" references found in the text either, confirming the figures are entirely unreferenced from prose.

## [FAIL] Broken References
- None found. All `\includegraphics` targets resolve to existing files on disk.

## [INFO] Unreferenced Figure Files
- None. Both files in `figures/` are included via `\includegraphics` in the paper.

## Additional Notes

### Figure Environment Details
| Figure | Environment | Placement | Width | Line |
|--------|------------|-----------|-------|------|
| 1 (`fig:architecture`) | `figure*` (full-width) | `[!t]` | 0.85\textwidth | 76-81 |
| 2 (`fig:pipeline`) | `figure*` (full-width) | `[!t]` | 0.85\textwidth | 175-180 |

### Figure Numbering
- Figure 1 appears in Section 2 (Environment Design), line 76. Sequential: OK.
- Figure 2 appears after Section 4.2 (Operational Metrics), line 175. Sequential: OK.
- Both use `figure*` (spanning two columns), consistent formatting.

### Table Labels (for cross-reference completeness)
- `tab:results` (line 123) - Main results table
- `tab:timing` (line 154) - Operational and injection metrics table
- `tab:rl` (line 233) - Preliminary RL training results (appendix)

### Cross-Reference Labels Verified
- `\ref{app:rl}` at line 204 references `\label{app:rl}` at line 221: OK.

## Summary
2 figures verified, 2 warnings (unreferenced labels), 0 failures.

Both figure files exist and have valid captions. The primary issue is that neither figure is cross-referenced from the paper text via `\ref{fig:...}` or hardcoded "Figure N" references. ICML reviewers may flag this as a formatting issue since standard practice requires in-text references to all figures (e.g., "as shown in Figure~\ref{fig:architecture}").
