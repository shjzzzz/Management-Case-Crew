---
name: case-design-audit
description: "Audit a single-case study design: case selection rationale, Yin validity/reliability, triangulation matrix and interview/data protocol. Use for 单一案例、单案例研究设计、案例选择、三角验证、建构效度、内部效度、外部效度、信度、证据链、访谈提纲、案例协议."
argument-hint: "[case company, research design or protocol]"
---

# Single-Case Design Audit (Yin / Eisenhardt Rigor)
1. Define the single-case rationale: why this enterprise/event (typical, extreme/outlier, revelatory, or longitudinal)? Define unit of analysis (group/subsidiary/transaction/tax cycle) and observation window.
2. Audit Yin's four quality criteria explicitly:
   - **Construct validity (建构效度):** Are key management/tax constructs (e.g. tax risk, internal control weakness, aggressive planning) operationalized with multiple sources of evidence and a clear chain of evidence?
   - **Internal validity (内部效度):** For explanatory/causal claims (e.g. why evasion occurred or how planning reduced ETR), are pattern matching (模式匹配), explanation building, and rival explanations (竞争性解释：行业周期、监管收紧、管理层更迭) addressed?
   - **External validity (外部效度):** Is generalization framed as **analytic generalization** (分析性概括：概括到管理理论/税收遵从机制), rather than statistical generalization?
   - **Reliability (信度):** Is there a reproducible case study protocol (访谈提纲、数据口径) and case database (`06-Data/`, `03-Literature/_sources/`)?
3. Build the **Evidence Triangulation Matrix (三角验证矩阵):** For each core claim, require >= 2 independent source types (e.g., audited financial statements + tax audit/penalty decisions + internal control manuals + semi-structured interviews).
4. Design interview protocol / survey items if primary data is planned, mapping each question to a theoretical dimension.
5. State the strongest defensible claim strength (descriptive vs. explanatory/mechanism) and any single-source caveats.

Delegation: detailed protocol drafting may be dispatched to `case-design-agent` (one agent at a time).
Do not run data calculations here; hand execution to `/case-data-analysis` only after the case protocol is approved.
