#!/usr/bin/env python3
"""Deterministic wiki checks for the Management Case Crew vault.

Usage:
    python wiki_lint.py lint [--vault PATH] [--json] [--strict]
    python wiki_lint.py map [--vault PATH] [--check] [--no-embed]
    python wiki_lint.py hash FILE [--vault PATH]

lint  : frontmatter, sources[] resolvability, broken wikilinks, orphan pages,
        index coverage, duplicate concept pages declared in Meta/aliases.csv. Scope = new research folders only (legacy tax-law
        notes are never scanned).
map   : generate Meta/folder-map.md (real folders) and Meta/link-map.md (wikilink graph: hubs,
        adjacency, orphans, broken links, duplicate names; legacy notes summarised per folder
        only) and refresh the compact map between ERC:MAP markers in CLAUDE.md and AGENTS.md.
        --check reports drift without writing (exit 1).
hash  : print SHA256 of FILE and report whether Meta/source-registry.md
        already contains it (exit 10 if already registered).

Exit codes: 0 ok, 1 errors found (or warnings with --strict), 10 hash already registered.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SCOPE = ["01-Research-Projects", "03-Literature", "04-Theories",
         "05-Methods", "08-Research-Notes", "09-Writing"]
SKIP_PARTS = {"_sources", ".obsidian", ".claude", ".agents", ".codex", ".git", "node_modules",
              "_vendor", "_erc-staging", "_erc-backups", "Templates"}
NEEDS_SOURCES = {"literature", "theory", "method", "synthesis", "query"}
PATH_EXT = (".pdf", ".md", ".txt", ".csv", ".dta", ".xlsx", ".html", ".epub", ".docx")
NON_PAGE_EXT = (".base", ".canvas", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".csv", ".dta", ".xlsx", ".docx")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")


def _strip_code_spans(text):
    return INLINE_CODE.sub("", CODE_FENCE.sub("", text))


def _resolve_wikilink(raw, stems, vault):
    cleaned = raw.strip().replace("\\", "/")
    no_ext = cleaned[:-3].lower() if cleaned.lower().endswith(".md") else cleaned.lower()
    hits = stems.get(_target(cleaned), [])
    if "/" in no_ext:
        return [h for h in hits
                if h.relative_to(vault).as_posix()[:-3].lower() == no_ext
                or h.relative_to(vault).as_posix()[:-3].lower().endswith("/" + no_ext)]
    return hits


def read(p):
    return p.read_text(encoding="utf-8-sig", errors="replace")


def parse_frontmatter(text):
    """Return (dict | None, error | None). None dict = no frontmatter."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return None, None
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return None, "malformed opening delimiter"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, "missing closing '---'"
    fm, key = {}, None
    for ln in lines[1:end]:
        if "\t" in ln:
            return fm, "tab character in frontmatter (YAML needs spaces)"
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if m and not ln.startswith((" ", "-")):
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                fm[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
            elif val == "":
                fm[key] = []
            else:
                fm[key] = val.strip("\"'")
        elif ln.lstrip().startswith("- ") and key is not None:
            if not isinstance(fm.get(key), list):
                fm[key] = []
            fm[key].append(ln.lstrip()[2:].strip().strip("\"'"))
    return fm, None


def _is_paper_version(rel):
    parts = [x.lower() for x in rel.parts]
    return any(parts[i] == "paper" and i + 1 < len(parts) and parts[i + 1] == "versions" for i in range(len(parts)))


def _is_project_entry(rel):
    """True for 01-Research-Projects/<project>/PROJECT.md (the single wiki entry page per project)."""
    return len(rel.parts) == 3 and rel.parts[0] == "01-Research-Projects" and rel.parts[2].lower() == "project.md"


def _is_project_subartifact(rel):
    """True for project-internal files (paper drafts, worklogs, analysis logs) under 01-Research-Projects/<project>/."""
    return len(rel.parts) >= 3 and rel.parts[0] == "01-Research-Projects" and not _is_project_entry(rel)


def _page_label(p, vault):
    """Human-readable node label; qualifies PROJECT.md with its project folder name."""
    rel = p.relative_to(vault)
    return "%s/PROJECT" % rel.parts[1] if _is_project_entry(rel) else p.stem


def md_files(root, dirs=None):
    bases = [root / d for d in dirs] if dirs else [root]
    for base in bases:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            rel = p.relative_to(root)
            if any(part in SKIP_PARTS or part.startswith("_erc") for part in rel.parts):
                continue
            if _is_paper_version(rel):
                continue
            yield p


def looks_like_path(s):
    return ("/" in s or "\\" in s or s.lower().endswith(PATH_EXT)) and not re.match(r"^(https?:|doi:|10\.\d)", s, re.I)


def _target(raw):
    """Lower-cased page name a [[wikilink]] target resolves to (folder and .md stripped)."""
    t = raw.strip().replace("\\", "/").split("/")[-1]
    return (t[:-3] if t.lower().endswith(".md") else t).lower()


def _stem_index(pages):
    stems = {}
    for p in pages:
        stems.setdefault(p.stem.lower(), []).append(p)
    return stems


def _index_targets(index_text):
    """Return (stems_set, rel_targets_set) extracted from [[wikilinks]] in Meta/index.md."""
    stems, rels = set(), set()
    for m in WIKILINK.finditer(index_text):
        raw = m.group(1).strip().replace("\\", "/")
        if raw.lower().endswith(".md"):
            raw = raw[:-3]
        low = raw.lower()
        rels.add(low)
        stems.add(low.split("/")[-1])
    return stems, rels


def lint(vault, strict=False):
    findings = []

    def add(level, page, check, msg):
        findings.append({"level": level, "file": str(page), "check": check, "msg": msg})

    text_cache = {}

    def read_cached(p):
        t = text_cache.get(p)
        if t is None:
            t = read(p)
            text_cache[p] = t
        return t

    scope_pages = sorted(md_files(vault, SCOPE))
    all_pages = list(md_files(vault))
    non_sub_pages = [p for p in all_pages if not _is_project_subartifact(p.relative_to(vault))]
    stems = _stem_index(all_pages)
    wiki_stems = _stem_index(non_sub_pages)

    index = vault / "Meta" / "index.md"
    index_text = read_cached(index) if index.exists() else None
    if index_text is None:
        add("warning", "Meta/index.md", "index", "Meta/index.md not found; index coverage not checked")

    wiki_scope_pages = [p for p in scope_pages if not _is_project_subartifact(p.relative_to(vault))]
    inbound = {p: set() for p in wiki_scope_pages}
    index_stems, index_rels = _index_targets(index_text) if index_text else (set(), set())

    for p in scope_pages:
        rel_path = p.relative_to(vault)
        rel = rel_path.as_posix()
        subartifact = _is_project_subartifact(rel_path)
        text = read_cached(p)
        fm, err = parse_frontmatter(text)
        if err:
            add("error", rel, "frontmatter", err)
        if not subartifact:
            if fm is None:
                add("warning", rel, "frontmatter", "no frontmatter")
            elif not err:
                ptype = str(fm.get("type", "")).lower()
                if not ptype:
                    add("warning", rel, "frontmatter", "missing 'type'")
                if ptype in NEEDS_SOURCES:
                    if "sources" not in fm:
                        add("warning", rel, "sources", "type '%s' requires a 'sources' field" % ptype)
                    if "verification" not in fm:
                        add("warning", rel, "verification", "missing 'verification' (verified|unverified)")
                srcs = fm.get("sources", [])
                if isinstance(srcs, str):
                    srcs = [srcs]
                for s in srcs:
                    if looks_like_path(s):
                        if not ((vault / s).exists() or (p.parent / s).exists()):
                            add("error", rel, "sources", "source path not found: %s" % s)
        for m in WIKILINK.finditer(_strip_code_spans(text)):
            target = _target(m.group(1))
            if not _resolve_wikilink(m.group(1), stems, vault) and not target.endswith(NON_PAGE_EXT):
                add("error", rel, "link", "broken wikilink [[%s]]" % m.group(1).strip())
        if not subartifact:
            if index_text is not None:
                if _is_project_entry(rel_path):
                    proj_name = rel_path.parts[1].lower()
                    in_idx = (proj_name in index_stems or (proj_name + "/project") in index_rels
                              or rel[:-3].lower() in index_rels)
                else:
                    in_idx = p.stem.lower() in index_stems
                if not in_idx:
                    add("warning", rel, "index", "not listed in Meta/index.md")
            same = wiki_stems.get(p.stem.lower(), [])
            if len(same) > 1 and not all(_is_project_entry(x.relative_to(vault)) for x in same):
                add("warning", rel, "duplicate", "file name is not unique in the vault, so [[%s]] is ambiguous" % p.stem)

    # inbound links may come from any page in the vault (index, MOC, notes), not only scope pages
    wiki_scope_set = set(wiki_scope_pages)
    for src in all_pages:
        try:
            src_text = read_cached(src)
        except OSError:
            continue
        for m in WIKILINK.finditer(_strip_code_spans(src_text)):
            for h in _resolve_wikilink(m.group(1), stems, vault):
                if h in wiki_scope_set and h != src:
                    inbound[h].add(src)

    # aliases.csv (canonical,alias): silent when absent or empty
    ali = vault / "Meta" / "aliases.csv"
    if ali.exists():
        for line in read(ali).splitlines()[1:]:
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
            canon, alias = parts[0].lower(), parts[1].lower()
            if canon != alias and canon in wiki_stems and alias in wiki_stems:
                add("warning", wiki_stems[alias][0].relative_to(vault).as_posix(), "alias",
                    "page [[%s]] is an alias of [[%s]] (Meta/aliases.csv); merge or link them" % (parts[1], parts[0]))

    for p, srcs in inbound.items():
        if not srcs:
            add("warning", p.relative_to(vault).as_posix(), "orphan", "no inbound links from any page (index, MOC or notes)")

    try:
        if cmd_map(vault, check=True, embed=False, quiet=True, graph=build_graph(vault, text_cache=text_cache)):
            add("warning", "Meta/link-map.md", "map", "folder-map / link-map missing or out of date; run: wiki_lint.py map --vault .")
    except OSError:
        pass

    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    return findings, len(scope_pages), errors, warnings


# ---------------------------------------------------------------- maps (folder map + wikilink map)
MAP_BEGIN = "<!-- ERC:MAP:BEGIN (generated by wiki_lint.py map; do not edit by hand) -->"
MAP_END = "<!-- ERC:MAP:END -->"
GRAPH_DIRS = SCOPE + ["MOC", "Meta"]
MAP_HIDDEN = {".obsidian", ".claude", ".agents", ".codex", ".git", ".agentero", "node_modules", "_vendor"}
GENERATED_MAPS = {"folder-map.md", "link-map.md"}
ROOT_RULE_FILES = {"claude.md", "agents.md"}
ROLES = {
    "00-Inbox": "待整理（含既有资料）",
    "01-Research-Projects": "案例研究项目（每项目一目录；PROJECT.md 为入口，论文在 paper/）",
    "03-Literature": "文献与案例资料笔记",
    "04-Theories": "管理学理论与分析框架笔记",
    "05-Methods": "单一案例与质性/财务测算方法笔记",
    "06-Data": "数据（raw 只读）",
    "07-Code": "财务/税负测算与编码脚本",
    "08-Research-Notes": "案例分析笔记与综合页",
    "09-Writing": "独立文稿（案例简报/评论/讲义，非项目主线）",
    "10-Archive": "已完成项目",
    "Meta": "规范、账本与机读状态",
    "MOC": "主题索引",
    "Templates": "模板",
}
READ_ONLY = {"06-Data/raw", "03-Literature/_sources"}
COMPACT_HUBS = 8
FULL_HUBS = 15
ADJ_CAP = 12


def _map_pages(vault):
    """(graph_pages, legacy_pages, all_pages) for the maps. Generated maps, root rule files
    (CLAUDE.md / AGENTS.md) and project-internal sub-artifacts (paper drafts/worklogs/logs under
    01-Research-Projects/<proj>/) are left out so regenerating never changes the graph and
    multi-project manuscripts do not pollute the cross-project wikilink graph."""
    def keep(p):
        rel = p.relative_to(vault)
        if any(part in MAP_HIDDEN for part in rel.parts):
            return False
        if len(rel.parts) == 1 and p.name.lower() in ROOT_RULE_FILES:
            return False
        if rel.parts[0] == "Meta" and len(rel.parts) == 2 and p.name in GENERATED_MAPS:
            return False
        if rel.parts[0] == "Meta" and len(rel.parts) > 1 and rel.parts[1] in ("backups", "extras"):
            return False
        if _is_project_subartifact(rel):
            return False
        return True
    graph = sorted(p for p in md_files(vault, GRAPH_DIRS) if keep(p))
    gset = set(graph)
    allp = sorted(p for p in md_files(vault) if keep(p))
    legacy = [p for p in allp if p not in gset]
    return graph, legacy, allp


def build_graph(vault, text_cache=None):
    graph, legacy, allp = _map_pages(vault)
    stems = _stem_index(allp)
    gset = set(graph)
    rel = lambda p: p.relative_to(vault).as_posix()
    out_edges = {p: [] for p in graph}      # resolved links to other graph pages
    inbound_any = {p: set() for p in graph}  # from any page
    inbound_res = {p: set() for p in graph}  # from research pages + MOC (not Meta)
    broken = []
    legacy_stat = {}
    for src in allp:
        try:
            text = text_cache[src] if (text_cache is not None and src in text_cache) else read(src)
        except OSError:
            continue
        in_graph = src in gset
        for m in WIKILINK.finditer(_strip_code_spans(text)):
            key = _target(m.group(1))
            if key.endswith(NON_PAGE_EXT):
                continue
            hits = _resolve_wikilink(m.group(1), stems, vault)
            if not hits:
                if in_graph:
                    broken.append((rel(src), m.group(1).strip()))
                continue
            for h in hits:
                if h == src:
                    continue
                if h in gset:
                    inbound_any[h].add(src)
                    if in_graph and rel(src).split("/")[0] != "Meta":
                        inbound_res[h].add(src)
                    if in_graph and h not in out_edges[src]:
                        out_edges[src].append(h)
                if not in_graph:
                    top = rel(src).split("/")[0]
                    st = legacy_stat.setdefault(top, {"links": 0, "to_graph": 0})
                    st["links"] += 1
                    if h in gset:
                        st["to_graph"] += 1
    dups = sorted((k, sorted(rel(p) for p in v)) for k, v in stems.items()
                  if len(v) > 1 and not all(_is_project_entry(p.relative_to(vault)) for p in v))
    dups = [(k, v) for k, v in dups if any((vault / x) in gset for x in v)]
    orphans = sorted(rel(p) for p in graph if not inbound_any[p] and rel(p).split("/")[0] not in ("Meta", "MOC"))
    return {"graph": graph, "legacy": legacy, "rel": rel, "out": out_edges, "in_any": inbound_any,
            "in_res": inbound_res, "broken": sorted(set(broken)), "dups": dups, "orphans": orphans,
            "legacy_stat": legacy_stat}


def _hubs(g, n):
    cand = [p for p in g["graph"] if g["rel"](p).split("/")[0] != "Meta"]
    cand.sort(key=lambda p: (-len(g["in_res"][p]), -len(g["out"][p]), g["rel"](p)))
    return [p for p in cand[:n] if g["in_res"][p] or g["out"][p]]


def _count_files(path, meta_dir_str):
    n_md = n_all = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in MAP_HIDDEN and not d.startswith("_erc"))
        is_meta = os.path.normcase(root) == meta_dir_str
        for f in files:
            if is_meta and f in GENERATED_MAPS:
                continue
            n_all += 1
            if f.lower().endswith(".md"):
                n_md += 1
    return n_md, n_all


def folder_entries(vault):
    """[(relpath, depth, n_md, n_all, role, flags)] for top-level dirs and their direct subdirs.
    Walks each subdirectory once and aggregates counts bottom-up into its top-level parent."""
    rows = []
    meta_dir_str = os.path.normcase(str(vault / "Meta"))
    tops = sorted(d for d in vault.iterdir()
                  if d.is_dir() and d.name not in MAP_HIDDEN and not d.name.startswith(".") and not d.name.startswith("_erc"))
    legacy_scope = set(SCOPE) | {"MOC", "Meta", "Templates"}
    for d in tops:
        is_meta = os.path.normcase(str(d)) == meta_dir_str
        n_md = n_all = 0
        subs = []
        for entry in sorted(d.iterdir(), key=lambda x: x.name):
            if entry.is_dir():
                if entry.name not in MAP_HIDDEN and not entry.name.startswith("_erc"):
                    subs.append(entry)
            else:
                if is_meta and entry.name in GENERATED_MAPS:
                    continue
                n_all += 1
                if entry.name.lower().endswith(".md"):
                    n_md += 1
        sub_rows = []
        for s in subs:
            sm, sa = _count_files(s, meta_dir_str)
            n_md += sm
            n_all += sa
            if not s.name.startswith("."):
                rp = d.name + "/" + s.name
                sub_rows.append((rp, 2, sm, sa, "", ["只读"] if rp in READ_ONLY else []))
        flags = []
        if d.name in READ_ONLY:
            flags.append("只读")
        if d.name not in legacy_scope and n_md:
            flags.append("旧资料：目录级汇总")
        rows.append((d.name, 1, n_md, n_all, ROLES.get(d.name, ""), flags))
        rows.extend(sub_rows)
    return rows


def render_folder_map(vault, entries=None):
    rows = folder_entries(vault) if entries is None else entries
    lines = ["---", "type: map", "status: generated", "---", "",
             "# 文件夹地图（自动生成）", "",
             "> 由 `python .claude/scripts/wiki_lint.py map` 生成，请勿手改；目录变化后重新运行。只统计磁盘上的实际目录；隐藏目录、`_erc*`、`_vendor` 不列出。", "",
             "| 路径 | 用途 | Markdown 页（磁盘） | 全部文件 | 标记 |", "|---|---|---|---|---|"]
    for rp, depth, nm, na, role, flags in rows:
        name = ("`%s/`" % rp) if depth == 1 else ("&nbsp;&nbsp;`%s/`" % rp)
        lines.append("| %s | %s | %d | %d | %s |" % (name, role, nm, na, "、".join(flags)))
    lines += ["", "## 检索约定",
              "- `只读`：不得修改；`旧资料：目录级汇总`：库内既有笔记，不逐页进双链图，只在目录一级汇总，按文件夹检索。",
              "- 检索既有笔记时排除 `06-Data`、`07-Code`、`.claude`、`.agents`、`_vendor`、`_erc-*`。",
              "- 论文工作在 `01-Research-Projects/<项目>/paper/`（outline.md、draft.md、versions/、reviews.json、final.md）；`Meta/citation-map.json` 与 `Meta/results-ledger.json` 只由 `paper_tools.py` 维护。", ""]
    return "\n".join(lines)


def _folder_summary(g):
    agg = {}
    for p in g["graph"]:
        top = g["rel"](p).split("/")[0]
        a = agg.setdefault(top, {"pages": 0, "out": 0, "in": 0, "orphans": 0})
        a["pages"] += 1
        a["out"] += len(g["out"][p])
        a["in"] += len(g["in_any"][p])
    for o in g["orphans"]:
        agg[o.split("/")[0]]["orphans"] += 1
    return agg


def render_link_map(vault, g=None):
    g = g or build_graph(vault)
    rel = g["rel"]
    n_links = sum(len(v) for v in g["out"].values())
    lines = ["---", "type: map", "status: generated", "---", "",
             "# 双链地图（自动生成）", "",
             "> 由 `python .claude/scripts/wiki_lint.py map` 生成，请勿手改。图只含研究库页面（研究文件夹、`MOC/`、`Meta/`）；既有笔记只在末尾做目录级汇总。页面名用反引号，避免这张图自己产生入链。", "",
             "## 概况",
             "- 图内页面 %d，页间链接 %d；断链 %d；无入链页 %d；重名主干名 %d。" % (len(g["graph"]), n_links, len(g["broken"]), len(g["orphans"]), len(g["dups"])),
             "- 用法：先读枢纽页，再沿“邻接表”展开；回答时注明来源页。", "",
             "## 枢纽页（被研究页与 MOC 链入最多）", "| 页面 | 路径 | 入链 | 出链 |", "|---|---|---|---|"]
    for p in _hubs(g, FULL_HUBS):
        lines.append("| `%s` | `%s` | %d | %d |" % (_page_label(p, vault), rel(p), len(g["in_res"][p]), len(g["out"][p])))
    lines += ["", "## 按文件夹", "| 文件夹 | 页数 | 出链 | 入链 | 无入链 |", "|---|---|---|---|---|"]
    for top, a in sorted(_folder_summary(g).items()):
        lines.append("| `%s` | %d | %d | %d | %d |" % (top, a["pages"], a["out"], a["in"], a["orphans"]))
    lines += ["", "## 邻接表（研究页 → 它链向的页面）"]
    for p in g["graph"]:
        if rel(p).split("/")[0] == "Meta" or not g["out"][p]:
            continue
        outs = sorted(_page_label(q, vault) for q in g["out"][p])
        more = "" if len(outs) <= ADJ_CAP else " …（另 %d 条）" % (len(outs) - ADJ_CAP)
        lines.append("- `%s` → %s%s" % (_page_label(p, vault), "、".join("`%s`" % o for o in outs[:ADJ_CAP]), more))
    lines += ["", "## 无入链页"] + (["- `%s`" % o for o in g["orphans"]] or ["- 无"])
    lines += ["", "## 断链"] + (["- `%s` → [%s]" % (a, b) for a, b in g["broken"]] or ["- 无"])
    lines += ["", "## 重名主干名（`[[链接]]` 指向不明，建议改名）"]
    lines += (["- `%s`：%s" % (k, "；".join("`%s`" % x for x in v)) for k, v in g["dups"]] or ["- 无"])
    lines += ["", "## 旧资料（目录级汇总，不进图）", "| 文件夹 | Markdown 页 | 页内链接 | 其中指向研究页 |", "|---|---|---|---|"]
    leg = Counter(rel(p).split("/")[0] for p in g["legacy"])
    for top in sorted(leg):
        st = g["legacy_stat"].get(top, {"links": 0, "to_graph": 0})
        lines.append("| `%s` | %d | %d | %d |" % (top, leg[top], st["links"], st["to_graph"]))
    if not leg:
        lines.append("| （无） | 0 | 0 | 0 |")
    lines.append("")
    return "\n".join(lines)


def render_compact(vault, g=None, entries=None):
    g = g or build_graph(vault)
    rows = [r for r in (folder_entries(vault) if entries is None else entries) if r[1] == 1]
    n_links = sum(len(v) for v in g["out"].values())
    L = [MAP_BEGIN, "## 知识地图（自动生成；完整版：`Meta/folder-map.md`、`Meta/link-map.md`）",
         "### 文件夹地图（实际磁盘）"]
    for rp, _, nm, na, role, flags in rows:
        tag = ("〔%s〕" % "、".join(flags)) if flags else ""
        L.append("- `%s/`%s：%d 页%s" % (rp, (" " + role) if role else "", nm, tag))
    L += ["### 双链地图（研究库）",
          "- 规模：%d 页、%d 条页间链接；断链 %d、无入链 %d、重名 %d。" % (len(g["graph"]), n_links, len(g["broken"]), len(g["orphans"]), len(g["dups"])),
          "- 枢纽页（入链/出链）：" + ("、".join("`%s`（%d/%d）" % (_page_label(p, vault), len(g["in_res"][p]), len(g["out"][p])) for p in _hubs(g, COMPACT_HUBS)) or "暂无"),
          "- 检索顺序：`Meta/index.md` 与枢纽页 → 沿 `[[链接]]` 展开（邻接表见 `Meta/link-map.md`）→ 回答注明来源页；既有笔记按文件夹检索，不进图。",
          MAP_END]
    return "\n".join(L)


def _rw(path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    return bom, crlf, s.replace("\r\n", "\n")


def _write(path, bom, crlf, s):
    if crlf:
        s = s.replace("\n", "\r\n")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))


def embed_block(path, block, check, limit=None):
    """Replace the marked map section in path. Returns 'unchanged' | 'updated' | 'drift' | 'no-markers' | 'too-big'."""
    if not path.exists():
        return "missing"
    bom, crlf, s = _rw(path)
    i, j = s.find(MAP_BEGIN), s.find(MAP_END)
    if i < 0 or j < i:
        return "no-markers"
    new = s[:i] + block + s[j + len(MAP_END):]
    if new == s:
        return "unchanged"
    if check:
        return "drift"
    size = len((new.replace("\n", "\r\n") if crlf else new).encode("utf-8")) + (3 if bom else 0)
    if limit and size > limit:
        return "too-big"
    _write(path, bom, crlf, new)
    return "updated"


def cmd_map(vault, check=False, embed=True, quiet=False, graph=None):
    g = graph if graph is not None else build_graph(vault)
    entries = folder_entries(vault)
    meta = vault / "Meta"
    if not check:
        meta.mkdir(exist_ok=True)
    drift = False
    say = (lambda *_a: None) if quiet else print
    for name, text in (("folder-map.md", render_folder_map(vault, entries)), ("link-map.md", render_link_map(vault, g))):
        p = meta / name
        cur = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") if p.exists() else None
        if cur == text:
            say("%s: unchanged" % name)
        elif check:
            say("%s: drift" % name)
            drift = True
        else:
            p.write_text(text, encoding="utf-8", newline="\n")
            say("%s: written" % name)
    if embed:
        block = render_compact(vault, g, entries)
        for fname, limit in (("CLAUDE.md", None), ("AGENTS.md", 24000)):
            r = embed_block(vault / fname, block, check, limit)
            say("%s: %s" % (fname, r))
            if r == "drift":
                drift = True
            if r == "too-big":
                say("  AGENTS.md would exceed %d bytes; shorten the map or CLAUDE.md" % limit)
    return 1 if drift else 0


def cmd_hash(vault, file):
    path = Path(file)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    print("sha256: " + digest)
    reg = vault / "Meta" / "source-registry.md"
    if reg.exists() and digest in read(reg).lower():
        print("status: ALREADY REGISTERED in Meta/source-registry.md")
        return 10
    print("status: new")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("lint")
    pl.add_argument("--vault", default=".")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--strict", action="store_true")
    pm = sub.add_parser("map")
    pm.add_argument("--vault", default=".")
    pm.add_argument("--check", action="store_true")
    pm.add_argument("--no-embed", action="store_true")
    ph = sub.add_parser("hash")
    ph.add_argument("file")
    ph.add_argument("--vault", default=".")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    if a.cmd == "hash":
        return cmd_hash(vault, a.file)
    if a.cmd == "map":
        return cmd_map(vault, a.check, not a.no_embed)
    findings, n, errors, warnings = lint(vault, a.strict)
    if a.json:
        print(json.dumps({"pages": n, "errors": errors, "warnings": warnings, "findings": findings}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print("[%s] %s (%s): %s" % (f["level"].upper(), f["file"], f["check"], f["msg"]))
        print("scanned %d pages: %d error(s), %d warning(s)" % (n, errors, warnings))
    return 1 if errors or (a.strict and warnings) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
