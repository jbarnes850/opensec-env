# Citation Verification Report
Generated: 2026-02-06

Paper: `/Users/jarrodbarnes/opensec-env/paper/opensec-arxiv/main.tex`
Bibliography: `/Users/jarrodbarnes/opensec-env/paper/opensec-arxiv/references.bib`

## [PASS] Verified Citations

All 14 citation keys in the paper resolve to entries in `references.bib`:

- `heelan2026exploit` -- cited lines 45 (\citep), 54 (\citet). Bib: author, title, year, howpublished present.
- `omdia2025agentic` -- cited line 50 (\citep). Bib: author, title, year, howpublished present.
- `aisoc2025survey` -- cited line 50 (\citep). Bib: author, title, year, journal, volume, number, pages, publisher present.
- `bernstein2002complexity` -- cited line 60 (\citep). Bib: author, title, year, journal, volume, number, pages, publisher, doi present.
- `tau2bench2025` -- cited lines 60 (\citet), 212 (\citep). Bib: author, title, year, journal present.
- `owasp2025agentic` -- cited line 190 (\citep). Bib: author, title, year, howpublished present.
- `anthropic2025injection` -- cited line 202 (\citep). Bib: author, title, year, howpublished present.
- `cyberseceval2` -- cited line 208 (\citep). Bib: author, title, year, howpublished present.
- `ctibench2024` -- cited line 208 (\citep). Bib: author, title, year, booktitle, url present.
- `excytin2025` -- cited line 208 (\citep). Bib: author, title, year, journal present.
- `cyborg2020` -- cited line 210 (\citep). Bib: author, title, year, journal present.
- `atlas2025` -- cited line 212 (\citep). Bib: author, title, year, journal present.
- `rlcyber2025survey` -- cited line 214 (\citep). Bib: author, title, year, howpublished present.
- `agenticai2026survey` -- cited line 214 (\citep). Bib: author, title, year, journal present.

## [WARN] Missing Fields

- `heelan2026exploit`: @misc -- no formal venue. Has `howpublished` (blog URL) and `note`. Acceptable for a blog post, but consider adding `month` for completeness.
- `omdia2025agentic`: @misc -- no formal venue. Has `howpublished` (blog URL) and `note`. Acceptable for an industry report.
- `owasp2025agentic`: @misc -- no formal venue. Has `howpublished` (blog URL) and `note`. Acceptable for a standards body publication.
- `anthropic2025injection`: @misc -- no formal venue. Has `howpublished` (research page URL) and `note`. Acceptable for a technical blog.
- `cyberseceval2`: @misc -- no formal venue. Has `howpublished` (research URL) and `note`. Note: CyberSecEval2 was published at EMNLP 2024. Consider upgrading to @inproceedings with `booktitle = {EMNLP}` for stronger citation.
- `rlcyber2025survey`: @misc -- no formal venue. Has `howpublished` (GitHub URL) and `note`. Acceptable for a curated resource list.
- `cyborg2020`: @article with `journal = {arXiv preprint arXiv:2002.10667}`. Note: CybORG has since been published in IJCAI workshop proceedings. Consider upgrading venue.
- `atlas2025`: @article with `journal = {arXiv preprint arXiv:2511.01093}`. Acceptable for a preprint.
- `agenticai2026survey`: @article with `journal = {arXiv preprint arXiv:2601.05293}`. Acceptable for a preprint.
- `tau2bench2025`: @article with `journal = {arXiv preprint arXiv:2506.07982}`. Acceptable for a preprint.
- `excytin2025`: @article with `journal = {arXiv preprint arXiv:2507.14201}`. Acceptable for a preprint.

## [FAIL] Broken References

None. All 14 \cite/\citet/\citep keys in the paper have corresponding entries in `references.bib`.

## [INFO] Unused Bibliography Entries

None. All 14 entries in `references.bib` are cited at least once in the paper.

## Citation Formatting Consistency

- **\citep vs \citet usage**: Consistent. `\citet` is used for grammatical subject position (2 instances: `heelan2026exploit` on line 54, `tau2bench2025` on line 60). `\citep` is used for parenthetical citations (all other instances). No `\cite` (bare) commands found.
- **Tilde spacing**: All `\citep` calls use `~\citep` (non-breaking space) when following text. Consistent throughout.
- **Multi-citation**: No multi-key citations (e.g., `\citep{a,b}`) used. Each citation is a separate command. This is acceptable but consider combining adjacent citations on line 50 (`\citep{omdia2025agentic}` and `\citep{aisoc2025survey}` in the same sentence) and line 214 (`\citep{rlcyber2025survey}` and `\citep{agenticai2026survey}` in the same sentence) into single multi-key citations for compactness.

## Summary

14 citations verified, 0 failures, 0 unused bibliography entries.

11 advisory warnings (missing formal venue on @misc entries and potential venue upgrades for entries with known published versions). None are blocking issues.

2 formatting suggestions (combining adjacent single-key citations into multi-key citations on lines 50 and 214).
