# Management Case Research Crew — Core Research & Routing Protocol

> Single source of truth for routing, management single-case argument spine, orchestration, writing constraints and evidence standards. Workspace layout and hard red lines live in `CLAUDE.md` / `Meta/vault-map.md`.

## 1. Intent Routing Table (17 Skills, 7 Agents)
| Stage / Role | User intent (examples) | Primary Skill | Authorized Agent |
|---|---|---|---|
| S1 Question | 选题、案例选择、核心管理/涉税问题界定 | `/research-question` | — |
| S2/S9 Literature | 文献综述、研究缺口、文献矩阵、Zotero/EndNote | `/literature-review` | `literature-agent` |
| S3 Framework | 分析框架、COSO/价值链/委托代理/治理机制 | `/theory-modeling` | `theory-agent` |
| S3 Tax Policy | 税法适用、偷漏税/稽查定性、税收筹划边界 | `/tax-policy-analysis` | `tax-policy-agent` |
| S4 Case Design | 单一案例设计、效度/信度、三角验证、访谈提纲 | `/case-design-audit` | `case-design-agent` |
| S5 Case Data | 财务指标、ETR/税负测算、同业对标、访谈编码 | `/case-data-analysis` | `case-data-agent` (only Bash/PS) |
| S6 Review | 盲审、审稿、挑刺、答辩预审、审查设计/稿件 | `/academic-review` | `academic-reviewer` (isolated) |
| S8 Outline | MBA论文大纲、主张清单、章节布局 | `/paper-outline` | — |
| S10 Draft | 起草论文、写初稿、分节写作 | `/paper-draft` | `paper-writer-agent` |
| S11 Refine / R&R | 精修、按盲审/导师意见修改、返修、R&R | `/paper-refine` | `paper-writer-agent` / `academic-reviewer` |
| S11b Polish | 润色、去 AI 味、语言精修、消除套话 | `/paper-polish` | — |
| Plots (MIT) | 出版级图表（Python）、图表/PDF 提取数据 | `/scientific-visualization`, `/thu-digitizer` | — |
| Wiki Ingest | 摄入来源到知识库、处理 `00-Inbox`/`_sources` | `/ingest-source` | — |
| Wiki Query | 知识库里有什么、根据知识库回答 | `/query-wiki` | — |
| Wiki Lint | 知识库体检、断链/孤立页/矛盾、周度复盘 | `/wiki-lint` | — |
| Director (S1–S12) | 完整做案例研究、规划推进、继续上次研究 | `/research-pipeline` | stage-gated (all above) |

## 2. Management Single-Case Argument Spine (S1–S12)
Keep one traceable spine across every MBA single-case thesis (`Meta/research-standards.md`):
`S1 Case & Issue` → `S2 Literature Gap` → `S3 Framework & Tax-Law Baseline` → `S4 Protocol, Triangulation & Wording Ceiling` → `S5 Financial/ETR Calculations, Coding & Results Ledger` → `S6 Independent Blind Review + 7-Mode Gate` → `S7 Researcher Go/Return/Stop` → `S8 Claim-Driven Outline` → `S9 Verified Citations & Locators` → `S10 Constrained Drafting` → `S11 Checklist Refine / R&R (+ /paper-polish)` → `S12 Final Gate, AI Disclosure & Wiki Write-back`.

Quality loop: research agents propose → `case-data-agent` executes → `academic-reviewer` challenges independently (artifacts only) → Director + researcher decide. A Fatal Flaw blocks acceptance; never jump to recommendations before diagnosing root causes with triangulated evidence.

## 3. Orchestration Layer
`/research-pipeline` maintains `01-Research-Projects/<project>/STATE.json` and `Meta/run-ledger.jsonl` **only** via `python .claude/scripts/orchestrator.py` (`init`, `status`, `next`, `artifact`, `verify`, `gate`, `fail`, `recover`, `enforce`, `log`).
- **Researcher gates**: never run `gate --decision pass` on AI judgment; always supply `--note`.
- **Retries & concurrency**: max 2 retries per agent per stage, then stop and report. Default concurrency 1 (S3: 2; cap 3). Claude Code hooks enforce order, retries, concurrency and file protection; follow voluntarily on agy/Codex.

## 4. Paper Writing & Human–AI Collaboration (S8–S12)
Follow `Meta/collaboration-protocol.md` (A0–A3, C1–C5) and `Meta/style-guide.md`:
- **Constrained inputs**: citations use `[@key]` from `Meta/citation-map.json` (with `locator` & `claim_scope` against L3 mismatch); numbers use `{{res:id}}` from `Meta/results-ledger.json` (honest null `--no-source-reason` when confidential/manual); result blocks carry `<!-- claim: Cn -->`; gaps become `⟦问：…⟧` (answered `⟦答：…⟧`), never invention.
- **Reference managers**: `paper_tools.py cite import|zotero|ris|csl|bib|open|zotero-note` exchanges with EndNote/Zotero (`ZOTERO_API_KEY` env-only, GET-only pulls; `zotero-note --yes` requires approval). Imported items start `unverified` (`manual` for Chinese).
- **Refinement (`/paper-refine`)**: `academic-reviewer` lists read files, judges literature by manuscript date, checks Frame-Lock and Concession Threshold (≥4/5, no consecutive concessions), and emits numbered `F1/M1/m1` + 5 scores (`ident, contrib, inst, consist, write`). Run `paper_tools.py review verify` before revising. Re-reviews use checklist counts (`--carried-*`/`--new-*`); accept only if Fatal ≤ prev, (Major < prev or tied Major with total ≥ prev), identical dimensions and no drop ≥2. New analysis goes to `Meta/review-queue.md`.
- **Language polish (`/paper-polish`)**: runs only after content settles; `polish check` proves citations, `{{res}}`, claim tags, Q/A markers and numbers are invariant. Never used to evade AI detection; disclose AI use in `paper/ai-disclosure.md`.
- **Isolation & failure gate**: every Skill/Agent declares `data_access_level` (`raw`/`redacted`/`verified_only`); `Meta/mechanism-library.md` offers analytical starting points, not evidence; S6/S12 must clear the 7-mode AI failure gate.

## 5. Case Study, Financial/Tax & Evidence Discipline
- **Single-case rigor (Yin)**: justify case selection, unit of analysis and time window; maintain a chain of evidence corroborated by triangulation (≥2 independent sources: audited reports + tax notices + interviews/internal controls).
- **Financial & tax calculations**: state exact formulas (ETR, VAT burden rate), fiscal years, accounting standard and peer benchmark sample; no silent adjustments; register key figures in `Meta/results-ledger.json`.
- **Tax planning vs. evasion**: separate lawful tax planning (business substance + statutory basis) from aggressive avoidance and illegal tax evasion (《税收征收管理法》第63条); Chinese tax-law claims require issuing authority, doc number, promulgation/effective dates, amendment/repeal status, scope and administrative-criminal boundary.

## 6. Knowledge Base & Wiki Maintenance
- Session start: read `Meta/purpose.md` (if blank, remind researcher; never invent direction), `Meta/decisions.md` and `Meta/constraints.md`.
- Routing & updates: `Meta/index.md` routes filesystem (`Meta/folder-map.md`) and knowledge graph (`Meta/link-map.md`); every ingest/lint pass updates `Meta/index.md` and appends to `Meta/log.md`. Search legacy notes by folder, not the link graph.
- Tier 1 frontmatter: `type` (`literature|theory|method|synthesis|query|research-project|dataset|analysis-plan|analysis-log`), `sources`, `updated`, `verification` (`verified|unverified`); literature notes add `cite_key`.
- Two-step ingest (`/ingest-source`): analyze & await approval → write/cross-link → update `Meta/index.md`, `Meta/source-registry.md` (SHA256) and `Meta/log.md`; log contradictions in `Meta/review-queue.md`.
- Deterministic checks & maps: run `python .claude/scripts/wiki_lint.py lint --vault .` and `python .claude/scripts/wiki_lint.py map --vault .`. After S12, compound key findings into `08-Research-Notes/` (`type: synthesis`) with researcher consent.
