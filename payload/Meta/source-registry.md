# Source Registry

| ID | Source | Type | URL / location | Access date | SHA256 | Notes |
|---|---|---|---|---|---|---|
| SRC-001 | Pre-existing tax-law notes in this vault | Local Markdown | vault root | | | Verify validity of each instrument |
| SRC-002 | National Laws and Regulations Database | Official legal | https://flk.npc.gov.cn/ | | | Check promulgation/effective dates |
| SRC-003 | State Taxation Administration | Official | https://www.chinatax.gov.cn/ | | | Prefer original notices |
| SRC-004 | National Bureau of Statistics | Official statistics | https://www.stats.gov.cn/ | | | Record table, release date, definition |
| SRC-005 | CNKI | Academic database | https://www.cnki.net/ | | | Verify metadata and full text |
| SRC-006 | Google Scholar | Discovery index | https://scholar.google.com/ | | | Verify against primary source |

> SHA256 由 `python .claude/scripts/wiki_lint.py hash <文件>` 生成；`/ingest-source` 用它判断来源是否已摄入。
