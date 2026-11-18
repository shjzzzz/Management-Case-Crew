---
name: case-data-analysis
description: "Plan, implement and validate single-case financial analysis, effective tax rate (ETR) calculations, peer benchmarking and qualitative interview coding. Use for 财务指标、杜邦分析、有效税率、ETR、税负率、税负测算、同业对标、访谈编码、质性编码、问卷统计、描述统计、数据清洗."
argument-hint: "[dataset, financial statements, transcripts or task]"
---

# Case Data & Tax Calculation Workflow
1. Inspect project files, data dictionary, and raw-data provenance (`06-Data/raw` or `03-Literature/_sources`).
2. Audit data grain, fiscal years, accounting standards (CAS/IFRS), consolidated vs. parent-company scope, and missingness.
3. Confirm exact formulas before computing:
   - Financial ratios (gross/net margin, ROE/DuPont, asset-liability ratio, operating cash flow).
   - Tax burden & ETR (e.g., GAAP ETR = income tax expense / pretax income; Cash ETR = cash taxes paid / pretax income; VAT/total tax burden = taxes paid / operating revenue).
   - Tax evasion / audit exposure (underpaid tax + late surcharge 0.05%/day + administrative penalty 0.5x–5x) or tax planning net benefit (tax saved minus restructuring/compliance cost).
   - Peer benchmark sample (industry classification, 3–5 comparable listed firms or industry averages).
4. Write an analysis plan (`Templates/analysis-plan.md`) before execution.
5. Implement reproducible Python/R/Stata scripts (or structured qualitative coding tables for interviews/documents); preserve raw inputs.
6. Run scripts only after confirming inputs/outputs.
7. Cross-check calculated numbers against original financial report footnotes and register key results via `paper_tools.py results`.
8. Produce tables, charts, logs, and environment info (`Templates/analysis-log.md`).
9. Record any deviations from the plan and reasons.

Delegation: long execution or coding may be dispatched to `case-data-agent` (invoking this Skill authorizes that, one agent at a time).
Never alter `06-Data/raw` or cherry-pick peer firms/years to exaggerate results.
