---
name: tax-policy-analysis
description: "Analyze Chinese tax law, tax evasion/non-compliance (偷漏税/虚开发票/稽查), tax planning boundaries and compliance impact. Use for 偷漏税、偷税、逃税、虚开发票、隐匿收入、税务稽查、税收筹划、税务筹划、税务风险、税法、增值税、企业所得税、个人所得税、税收优惠、核定征收、税收遵从、法律依据."
argument-hint: "[tax issue, case fact pattern or statutory question]"
---

# Tax Law, Tax Evasion & Tax Planning Analysis
1. Identify the tax types (VAT, CIT, IIT, etc.), transaction structure, taxpayer identity, and exact tax periods.
2. Trace authoritative Chinese tax law sources (Law, Administrative Regulation, Departmental Rule, Normative Document, Judicial Interpretation) with issuing authority, document number (文号), promulgation/effective dates, and current validity. Mark unverified texts as "未核实".
3. Apply tax-law conflict-resolution rules where needed (税收法定、实质重于形式、法律优位、特别法优于普通法、新法优于旧法、实体法不溯及既往、程序从新).
4. Draw the **Compliance Boundary** explicitly:
   - **Lawful Tax Planning (合法税收筹划):** genuine business substance, ex-ante restructuring, statutory preferential policy fit.
   - **Tax Avoidance / Aggressive Position (避税/激进筹划):** anti-avoidance adjustment risk (《企业所得税法》第47条等).
   - **Illegal Tax Evasion (偷漏税/虚开发票):** 《税收征收管理法》第63条定性、补税 + 滞纳金 (0.05%/日) + 罚款 (0.5–5倍)、纳税信用降级、以及《刑法》第201/205条行刑衔接风险。
5. Quantify or map the financial/governance implications and state what official documents or tax-authority confirmations are still needed.

Delegation: detailed statutory and compliance analysis may be dispatched to `tax-policy-agent` (one agent at a time).
Never provide instructions for illegal tax evasion; frame evasion analysis strictly around compliance diagnosis and governance remediation.
