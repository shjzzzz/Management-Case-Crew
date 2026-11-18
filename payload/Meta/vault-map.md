---
inbox: 00-Inbox
projects: 01-Research-Projects
resources: .
literature: 03-Literature
literature_raw: 03-Literature/_sources
theories: 04-Theories
methods: 05-Methods
data_raw: 06-Data/raw
data_processed: 06-Data/processed
code: 07-Code
notes: 08-Research-Notes
writing: 09-Writing
archive: 10-Archive
templates: Templates
meta: Meta
moc: MOC
---

# Vault Map

- `literature_raw` holds immutable original sources (PDFs, clips); never edit them.
- Paper work lives in `01-Research-Projects/<project>/paper/` (outline.md, draft.md, versions/, reviews.json, final.md). `Meta/citation-map.json` and `Meta/results-ledger.json` are maintained only by `paper_tools.py`.
- `resources: .` keeps the vault root and its pre-existing layout; do not move or rename existing notes.
- When searching tax-law notes, exclude `.claude`, `_vendor`, `_erc-staging`, `_erc-backups`, `06-Data`, `07-Code`.
- If this file pre-existed, the installer keeps it; compare mappings manually.
- This YAML schema is this package's own; if you enable the upstream framework, check its expected keys against its docs.
