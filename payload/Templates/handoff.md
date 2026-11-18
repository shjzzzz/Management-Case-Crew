---
type: handoff
project: ""
stage: S1
agent: ""
created: YYYY-MM-DD
---

# 交接单（Research Director → Agent）

> 派出 Agent 时，把下面各项写进给它的提示；不要把自己的推理过程、结论倾向或“你应该得出什么”塞给独立审查方。

## 1. 任务（一句话）
<!-- 例：核实 2018 年后个人所得税征管数字化相关的实证文献，输出文献矩阵 -->

## 2. 输入产物（只给路径，不给推理）
- `Meta/purpose.md`
- `01-Research-Projects/<项目>/PROJECT.md`
- 前序阶段产物（路径，来自 `orchestrator.py status`）：

## 3. 范围与禁止项
- 范围：
- 不得修改 `06-Data/raw`、`03-Literature/_sources`；不得编造文献、法条、数据或结果。

## 4. 期望输出
- 形式（文件路径 / 表格 / 分级意见）：
- 必须包含：来源与核实状态；不确定之处单列；未核实清单。

## 5. 完成后（Director 执行）
（`ORC` = `orchestrator.py` 命令，路径与用法见 `/research-pipeline`：Claude Code 为 `.claude/scripts/`，agy / Codex 为 `.agents/scripts/`。）
1. 把产物登记到阶段：`ORC artifact <路径>`
2. `ORC verify`；未满足则按 `next` 提示补齐。
3. 失败时：`ORC fail --agent <名> --reason "<原因>"`，最多重试 2 次，仍失败就停下向研究者报告。
4. 向研究者汇报产物与关卡问题，**等研究者表态后**再 `gate`。
