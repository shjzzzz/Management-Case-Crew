---
name: case-design-audit
description: "Audit a single-case study design: case selection rationale, Yin validity/reliability, triangulation matrix, rival explanations, interview/data protocol and permissible wording ceiling. Use for 单一案例、单案例研究设计、案例选择、三角验证、建构效度、内部效度、外部效度、信度、证据链、访谈提纲、案例协议."
argument-hint: "[case company, research design or protocol]"
data_access_level: redacted
task_type: open-ended
---

# Case Design Audit（S4：单一案例研究设计与三角验证审查）

## 1. 目标与边界
依据 Yin / Eisenhardt 单一案例方法论审查研究设计，形成冻结的 `analysis-plan.md`（案例协议、三角验证矩阵与允许措辞上限），为 S5 财务/税负测算与访谈编码提供硬基准。**本 Skill 不跑测算代码，计划冻结后才交 `/case-data-analysis`。**

## 2. 前置读取
- 读取 `Meta/purpose.md`、`Meta/decisions.md`、`Meta/constraints.md`、`Meta/research-standards.md` 及项目 `PROJECT.md`、S2 缺口表、S3 管理分析框架与税法底线。

## 3. 核心审查流程与委派
- **委派授权**：详细案例协议起草与效度审计可派出 `case-design-agent`（按 `Templates/handoff.md` 交接，一次一个）。
1. **案例选择理由与边界**：论证为何选该单一案例（典型性 / 极端性 / 启示性 / 纵向追踪），明确分析单位（集团/子公司/交易链/税期）与观察窗口。
2. **Yin 四大质量标准审查**：
   - **建构效度**：核心构念（税务风险、内控缺陷、激进筹划/偷漏税诱因）是否有多源证据与完整证据链？
   - **内部效度**：归因诊断是否设计了模式匹配、解释构建与竞争性解释排查（行业周期、监管收紧、一次性补贴、管理层更迭）？
   - **外部效度**：是否严格限定为**分析性概括**（概括至管理与税收遵从理论），而非统计外推？
   - **信度**：是否建立了可复现的案例协议（数据口径、访谈提纲、编码规则）与案例数据库？
3. **证据三角验证矩阵**：每条核心命题须绑定 ≥2 类独立证据源（经审计财报/纳税申报/稽查文书 + 内控制度/合同 + 访谈/公开披露/同业对标），并写明**证伪标准**。
4. **访谈提纲与编码映射**：若涉及一手访谈/问卷，将每道问题映射到 S3 理论维度并注明匿名化与保密规则。
5. **锁定措辞上限与冻结计划**：明确标注本项目最高可辩护的措辞强度（多源三角验证归因 / 初步提示 / 理论推演），按 `Templates/analysis-plan.md` 写入并冻结。

## 4. 产出与知识回流
- 输出：案例设计审查报告、冻结的 `01-Research-Projects/<项目>/analysis-plan.md`（含三角验证矩阵与措辞上限）、访谈/编码协议、待补证据缺口；必要时将通用方法沉淀至 `05-Methods/`。

## 5. 硬性禁止
禁止在本阶段执行数据测算脚本；禁止编造访谈记录或三角验证链路；禁止把单一来源包装成已验证的因果归因。
