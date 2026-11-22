---
name: case-data-analysis
description: "Plan, implement and validate reproducible single-case financial analysis, effective tax rate (ETR) and tax burden calculations, peer benchmarking, qualitative interview coding and results-ledger registration. Use for 财务指标、杜邦分析、有效税率、ETR、税负率、税负测算、同业对标、访谈编码、质性编码、问卷统计、描述统计、数据清洗."
argument-hint: "[dataset, financial statements, transcripts or task]"
data_access_level: raw
task_type: open-ended
---

# Case Data Analysis（S5：可复现财务/税负测算、同业对标与质性编码）

## 1. 目标与边界
严格依据 S4 冻结的 `analysis-plan.md` 执行财务比率、有效税率（ETR）、税负与稽查风险/筹划净收益测算、同业对标及访谈/内控质性编码，并将核心数值登记至 `Meta/results-ledger.json`。**绝不修改 `06-Data/raw` 或 `03-Literature/_sources`，绝不挑选年份或对标企业夸大结论。**

## 2. 前置读取
- 读取项目 `PROJECT.md`、冻结的 `analysis-plan.md`、`Meta/constraints.md`、`Meta/research-standards.md` 及 `06-Data/metadata/` 数据卡。

## 3. 核心执行流程与委派
- **委派授权**：完整脚本编写、运行测算与质性编码可派出 `case-data-agent`（唯一拥有 Bash/PowerShell 权限的执行 Agent，一次一个）。
1. **原始数据与口径审计**：核查 `06-Data/raw` 或 `03-Literature/_sources` 中的报表会计准则（CAS/IFRS）、合并/母公司口径、会计年度、缺失与重述情况。
2. **测算公式前置确认**：
   - 财务比率（毛利率、净利率、ROE/杜邦拆解、资产负债率、经营现金流）；
   - 税负与 ETR（GAAP ETR = 所得税费用 / 利润总额；Cash ETR = 支付税费 / 利润总额；增值税/综合税负率 = 实缴税额 / 营业收入）；
   - 偷漏税风险敞口（补税 + 滞纳金 0.05%/日 + 0.5–5 倍罚款）或合法筹划净收益（节税额扣除业务重组与合规成本）；
   - 同业对标样本（行业分类、3–5 家可比上市公司或行业均值，明确筛选规则）。
3. **可复现脚本与编码执行**：编写模块化 Python / R / Stata 脚本存入 `07-Code/<lang>/<project>/`，运行写文件脚本前先说明输入与输出；衍生数据仅写入 `06-Data/processed/`。质性访谈/制度按编码表逐条保留出处编号。
4. **复核与结果入簿**：将脚本输出与原始财报附注逐项核对，运行 `python .claude/scripts/paper_tools.py results import/register` 登记全部待引用核心数值（保密/手工来源使用 `--no-source-reason` 诚实登记）。
5. **记录日志与偏离**：按 `Templates/analysis-log.md` 写入 `analysis-log.md`，如实记录样本/口径核算、软件版本、敏感性检验与对冻结计划的任何偏离。

## 4. 产出与知识回流
- 输出：模块化脚本、衍生表图、`analysis-log.md`、已登记的 `Meta/results-ledger.json` 条目；如发现原始口径矛盾或数据冲突，同步记入 `Meta/review-queue.md`。

## 5. 硬性禁止
禁止修改 `06-Data/raw` 或 `03-Literature/_sources`；禁止静默删样本或挑选对标样本；禁止心算或未入簿直接写论文核心数字；禁止将未公开企业/个人敏感数据发送至外部服务。
