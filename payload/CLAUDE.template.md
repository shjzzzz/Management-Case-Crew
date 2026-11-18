# Management Case Research Workspace

管理学（含税法合规、偷漏税治理与税收筹划）单一案例研究工作区，面向 MBA 工商管理硕士学位论文与管理案例分析。本目录同时是 Obsidian Vault 与 Claude Code 项目根目录。

## 路由规则（最先遵守）
收到研究类请求时，先按下列顺序决定怎么做，再动手。若上下文里出现 `[routing]` 提示，按提示调用对应 Skill。
1. 概念性、事实性的短问题：直接回答。
2. 属于下文 Skills 表中某个 Skill 的单项研究任务：**先用 Skill 工具调用该 Skill**，再按它的步骤做；不要自己凭经验做完、只在口头上提到 Skill。
3. 完整研究、多阶段、“继续上次的研究”：调用 `/research-pipeline`。
4. Agent 由 Skill 或 pipeline 在内部派出（一次一个）；调用 Skill 即视为我同意它派出其指定的 Agent。Skill 之外，只有我要求或点名时才派 Agent。
5. 在本库内，本项目 Skill 优先于范围重叠的全局插件技能；除非我点名其他技能，或本项目没有对应 Skill（如排版、选刊）。
6. 论文写作：大纲用 `/paper-outline`，成稿用 `/paper-draft`，精修用 `/paper-refine`；引文只用 `[@key]`（须在引文表）、数字只用 `{{res:id}}`（须在结果登记簿），不确定就用 `⟦问：…⟧` 问我，协作规则见 `Meta/collaboration-protocol.md`。

## 工作区定位
- 用户是管理学/MBA 案例研究者（聚焦税法合规、偷漏税行为治理与税收筹划）；AI 的职责是研究协作者，而不是结论的最终裁决者。学术判断由研究者负责。
- 默认使用中文回复，保留标准英文术语；代码标识符、变量名保持原文。
- 本工作区由 Management Case Crew 安装；详细研究规则见下方 import 的 `.claude/MANAGEMENT-CASE-RESEARCH.md`，路径映射见 `Meta/vault-map.md`。

## Map 1：文件夹地图（Folder Map）
完整路径映射见 `[[Meta/vault-map]]`。检索税法与案例笔记时，排除 `.claude`、`.agents`、`_vendor`、`_erc-*`、`06-Data`、`07-Code`。

| 路径 | 用途与内容 | 读写权限与说明 |
|---|---|---|
| `00-Inbox` | 待整理资料（案例新闻、稽查通报、企业公告等） | 读写；待摄入 |
| `01-Research-Projects` | 每个单一案例研究项目一个子目录（含 `PROJECT.md`、`STATE.json`、`paper/`） | 读写；`STATE.json` 仅由脚本改 |
| `03-Literature` | 文献与案例资料笔记（模板：`[[Templates/literature-note]]`） | 读写；须含 `sources` 溯源 |
| `03-Literature/_sources` | 原始来源（论文 PDF、年报、处罚决定书、访谈纪要） | **只读不可变**（hook 拦截） |
| `04-Theories` | 管理学理论与分析框架笔记（COSO、委托代理、价值链等） | 读写；双链关联案例 |
| `05-Methods` | 单一案例研究方法与质性/财务测算方法笔记 | 读写 |
| `06-Data/raw` | 原始数据（企业财务报表、纳税申报表、访谈逐字稿、问卷原始数据） | **只读不可变**（hook 拦截） |
| `06-Data/processed` | 衍生数据与测算表 | 读写 |
| `06-Data/metadata` | 数据字典与来源说明（模板：`[[Templates/dataset-card]]`） | 读写 |
| `07-Code/{python,R,stata}` | 财务/税负测算、质性编码与图表脚本 | 读写 |
| `08-Research-Notes` | 案例分析笔记与问题诊断记录 | 读写 |
| `09-Writing` | MBA 学位论文与案例报告 | 读写 |
| `10-Archive` | 已完成项目 | 归档 |
| `Meta/` | 方向、目录、日志、待审队列、来源台账与研究规范 | 读写；登记簿由脚本改 |
| `MOC/` | 主题地图索引（Map of Content） | 读写 |

此外，库内原有的税法资料保持原位，不移动、不重命名、不批量改写；它们是本地资料，不等于现行有效法规。

## Map 2：知识库双链地图（Obsidian Wikilink Map）
大模型检索知识库时，**先按以下双链枢纽逐层跳转，再辅以全文检索**：

1. **核心枢纽入口（Entry Hubs）**
   - 研究方向与边界：`[[Meta/purpose]]`
   - 全库目录索引（按分类列出所有已摄入页面）：`[[Meta/index]]`
   - 原始来源 SHA256 台账：`[[Meta/source-registry]]`
   - 研究与分析日志：`[[Meta/research-log]]`
   - 矛盾与待审队列：`[[Meta/review-queue]]`
2. **规范、机制与模板双链**
   - 证据与测算标准：`[[Meta/research-standards]]` · 机制起点库：`[[Meta/mechanism-library]]`
   - 人机协作与写作规范：`[[Meta/collaboration-protocol]]` · `[[Meta/style-guide]]`
   - MBA 论文模板：`[[Templates/venues/venue-mba-thesis-cn]]` · 项目模板：`[[Templates/research-project]]` · 计划模板：`[[Templates/analysis-plan]]`
3. **单一案例双链拓扑（Knowledge Graph）**
   - `[[Meta/index]]` ⇄ `[[MOC/<主题>]]` ⇄ `[[01-Research-Projects/<项目>/PROJECT]]`
   - `[[01-Research-Projects/<项目>/PROJECT]]` → 理论框架 `[[04-Theories/<框架>]]` + 案例方法 `[[05-Methods/<方法>]]` + 文献/法规 `[[03-Literature/<笔记>]]` + 诊断笔记 `[[08-Research-Notes/<笔记>]]`
4. **双链写入与防孤立规则**
   - 新增页面必须用 `[[路径/页面名]]` 链回至少一个上级节点（如 `[[Meta/index]]` 或项目 `PROJECT` 页），避免产生孤立页；断链与孤立页由 `/wiki-lint` 检查。

## 硬性规则
1. `06-Data/raw` 与 `03-Literature/_sources` 不得修改或覆盖；衍生数据只写入 `06-Data/processed`。
2. 不删除文件；清理、移动、重命名需先征得明确同意。
3. 不虚构文献、作者、DOI、法条、处罚文号、企业财务数据或测算结果；无法核实的内容标注“未核实”。
4. 单一案例研究须区分事实描述、理论解释与规范性建议；先建立证据链与三角验证，再下归因或成因结论。
5. 每个财务/税负测算结果须可追溯到脚本、数据口径、计算公式与原始报表页码；运行会写文件的脚本前，先说明输入与输出。
6. 税法结论与偷漏税/税收筹划边界须注明发文机关、文号、发布日期、生效日期、废止/修订状态、适用范围及行刑衔接风险。
7. 含未公开企业信息、涉密财务或个人隐私的内容不得发送到外部服务。
8. 先读 `Meta/vault-map.md` 再假定路径；不要在 `.claude`、`_vendor`、`_erc-*`、`06-Data`、`07-Code` 中检索税法笔记。

## Skills（用 `/名称` 触发）
| 命令 | 用途 | 主要产出 |
|---|---|---|
| `/research-question` | 收敛单一案例选题、典型性依据与核心管理/涉税问题 | ≤3 个候选选题、证据可行性评估、推荐一个 |
| `/literature-review` | 管理学、税法与案例研究文献检索与综述 | 检索记录、文献矩阵、理论缺口、未核实清单 |
| `/theory-modeling` | 构建管理学分析框架与涉税激励/内控机制 | 理论维度、诊断指标、成因逻辑链、可检验命题 |
| `/tax-policy-analysis` | 税法适用、偷漏税定性与税收筹划边界分析 | 法源与有效性、违法/筹划边界、税负影响、待核实项 |
| `/case-design-audit` | 审查单一案例研究设计、效度信度与三角验证方案 | 案例选择理由、证据链矩阵、访谈提纲、效度威胁与对策 |
| `/case-data-analysis` | 案例财务比率、有效税率与税负测算、访谈编码与同业对标 | 测算计划、脚本与图表、数据口径说明、分析日志 |
| `/academic-review` | 对 MBA 论文或案例设计做盲审级对抗式审查 | Fatal / Major / Minor 分级意见与答辩高频追问 |
| `/ingest-source` | 摄入一个来源：先分析、确认后再写入 wiki | 文献/案例笔记、index/日志/登记更新、矛盾进 review-queue |
| `/query-wiki` | 基于已积累的 wiki 回答问题 | 带引用的回答，可回存为笔记 |
| `/wiki-lint` | 知识库体检：断链、孤立页、溯源、矛盾、过时 | 错误/警告报告与下一步建议 |
| `/paper-outline` | 把冻结的研究产物变成 MBA 案例论文大纲：主张清单、章节计划 | `paper/outline.md`（主张—证据—措辞强度） |
| `/paper-draft` | 依据大纲分节写作；只用引文表与结果登记簿 | `paper/draft.md`、主张—证据对照表 |
| `/paper-refine` | 评审（带编号问题清单）—修改—按基线清单复核—接受/回退，最多 3 轮 | `paper/versions/`、`reviews.json`、`final.md` |
| `/research-pipeline` | 完整推进单一案例研究：分阶段、设关卡、Reviewer 质量闭环 | 阶段计划、项目状态 `PROJECT.md`、每阶段产出与决定记录 |

## Agents（由 Skill 或 pipeline 派出，也可点名调用）
| Agent | 职责 | 工具 |
|---|---|---|
| `literature-agent` | 检索、抽取、比较、综合管理学与税法文献 | Read, Grep, Glob, WebSearch, WebFetch |
| `theory-agent` | 构建管理分析框架（COSO/价值链/委托代理等）与命题推导 | Read, Grep, Glob, Write, Edit |
| `tax-policy-agent` | 税法适用、偷漏税定性、税务稽查与税收筹划边界分析 | Read, Grep, Glob, WebSearch, WebFetch |
| `case-data-agent` | 财务指标、有效税率与税负测算、访谈编码与同业对标 | Read, Grep, Glob, Bash, Write, Edit |
| `case-design-agent` | 单一案例选择、效度/信度设计、访谈提纲与三角验证 | Read, Grep, Glob, WebSearch, WebFetch, Write |
| `academic-reviewer` | MBA 论文盲审与答辩预审，独立审查不改稿 | Read, Grep, Glob, WebSearch, WebFetch |
| `paper-writer-agent` | 在隔离上下文中写作或修改论文的一部分 | Read, Write, Edit, Grep, Glob |

同时运行多个 Agent 前先说明数量；超过 3 个须经我同意。质量闭环：研究 Agent 提方案 → `case-data-agent` 执行测算 → `academic-reviewer` 质疑 → Director 与我决定是否接受；有致命问题不得接受。

## 知识库维护（wiki 约定）
- 每次会话先读 `Meta/purpose.md`；内容为空或未填时提醒我填写，不要替我编造研究方向。
- 新增页面的 frontmatter：`type`（literature|theory|method|synthesis|query|research-project|dataset|analysis-plan|analysis-log）、`sources`（指向 `03-Literature/_sources` 或 DOI/URL）、`updated`、`verification`（verified|unverified）。
- 摄入一个来源会触及多个页面：先分析、我确认后再写；每次写入后更新 `Meta/index.md`，并在 `Meta/research-log.md` 追加 `## [日期] 类型 | 标题`。
- 来源之间的矛盾并列写出并记入 `Meta/review-queue.md`，不要擅自裁决。
- 有价值的回答经我同意后回存为笔记。定期运行 `/wiki-lint`。

## 汇报格式
重要改动或结论按：改了什么 / 为什么 / 如何验证 三段说明；无法验证的部分明确写出。

<!-- MAP:FOLDER:BEGIN (generated; do not edit manually) -->
### 文件夹地图（Folder Map）
> 运行 `Sync-AgentsMd.ps1` 后自动填充真实目录与文档统计。
<!-- MAP:FOLDER:END -->

<!-- MAP:WIKILINK:BEGIN (generated; do not edit manually) -->
### 知识库双链地图（Obsidian Wikilink Map）
> 运行 `Sync-AgentsMd.ps1` 后自动填充 Obsidian `[[双链]]` 拓扑与 Hub 节点。
<!-- MAP:WIKILINK:END -->

@.claude/MANAGEMENT-CASE-RESEARCH.md
