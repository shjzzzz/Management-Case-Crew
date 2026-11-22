#!/usr/bin/env python3
"""Paper-writing support: citation table, results ledger, refinement decisions, checks, report.

Standard library only. Inspired by the idea (not the code) of PaperOrchestra: the writer may only
cite keys that exist in a verified citation table, and every number must trace to registered results.

  cite add --key K --title T [--authors "A; B"] [--year Y] [--doi D] [--venue V]
           [--type article|book|chinese|legal] [--doc-no NO --effective DATE] [--offline]
  cite from-note NOTE.md... [--offline] [--replace]
                                              bridge 03-Literature/*.md frontmatter into citation-map.json
  cite verify [--key K | --all] [--offline]   re-check unverified/mismatch entries against Crossref
  cite confirm --key K --note TEXT            the researcher confirms a source by hand (asks for permission)
  cite check DRAFT.md...                      unknown keys (error), unverified keys (warning), unused entries
  cite bib [-o refs.bib]                      BibTeX of the table
  cite ris [-o refs.ris] | cite csl [-o refs.json]   export for EndNote / Zotero / Word
  cite import FILE... [--format auto|ris|bibtex|csl] [--no-notes] [--attach] [--pdf-dir DIR] [--verify] [--replace] [--dry-run]
                                              import an EndNote/Zotero export (RIS, BibTeX, CSL-JSON): entries start
                                              unverified, literature notes are created, PDFs copied to _sources with --attach
  cite zotero [--user ID | --group ID | --base-url URL] [--collection KEY] [--limit N] [...]
                                              pull from the local Zotero API (default) or the Zotero web API (GET only;
                                              API key only from env ZOTERO_API_KEY); --query Q [--list] searches, --item KEY pulls one,
                                              --notes appends the item's Zotero notes to its literature note
  cite open KEY [--print]                     open the PDF kept in 03-Literature/_sources with the system viewer
  cite zotero-note KEY [--zotero-key K] [--user ID|--group ID] [--yes]
                                              write the literature note back as a NEW child note in Zotero (preview unless --yes;
                                              needs a write-enabled ZOTERO_API_KEY; never edits or deletes existing items)
  cite list
  results register --id ID --value V [--label L --se S --n N --source FILE --script FILE --no-source-reason T --note T]
  results import CSV --prefix P --source FILE [--script FILE]   register every cell as P.<row>.<col>
  results render DRAFT.md [-o OUT.md]         fill {{res:id}} / {{res:id:3}} placeholders from the ledger
  results check DRAFT.md...                   unknown ids, stale sources, bare statistics not linked to results
  review verify --review R.md --manuscript M.md [--offline] [--strict] [--json]
                                              verify reviewer quotes against manuscript (NFC) & suggested references
  refine start DRAFT.md                       snapshot paper/versions/v0.md
  refine record --version vN --fatal F --major M --minor m --scores a=5,b=6
                                              record a review and get the accept / revert decision
  refine status
  polish scan DRAFT.md... [--strict]          list AI-writing tells (patterns from Meta/ai-tells.json); advisory
  polish check --before A.md --after B.md     a language pass must leave citation keys, {{res}} placeholders,
                                              claim tags, question markers and every number unchanged
  questions DRAFT.md...                       unanswered researcher questions (marker for researcher: see below)
  report                                      metrics: citations verified, numbers linked, open questions, rounds

Markers: AI asks the researcher with  ⟦问：...⟧ ; the researcher answers with  ⟦答：...⟧ right after it.
Citations in drafts use pandoc keys: [@key] or [@a; @b]. Numbers use {{res:id}}.
Network: Crossref public API only, sending the title/DOI of the CITED work (never project content),
generic User-Agent, no credentials. Disable with --offline or ERC_OFFLINE=1.
"""
import argparse
import csv
import datetime
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import orchestrator as orc  # noqa: E402

MAP_REL = os.path.join("Meta", "citation-map.json")
RES_REL = os.path.join("Meta", "results-ledger.json")
OK_STATUS = {"verified", "confirmed"}
MAX_ROUNDS = 3
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_:\-]*$")
CITE_GROUP = re.compile(r"\[([^\[\]]*@[^\[\]]*)\]")
CITE_KEY = re.compile(r"@([A-Za-z][A-Za-z0-9_:\-]*)")
PLACEHOLDER = re.compile(r"\{\{res:([A-Za-z0-9_.\-:]+?)(?::(\d+))?\}\}")
Q_RE = re.compile(r"⟦问：(.*?)⟧", re.S)
A_RE = re.compile(r"⟦答：(.*?)⟧", re.S)
STAT_RE = re.compile(r"(?<![\w.])(\d+\.\d+|\d+(?:\.\d+)?\s*%)")
SAFE_DECIMALS = {"0.01", "0.05", "0.1", "0.10", "0.001"}


# ------------------------------------------------------------------ io helpers
def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def vault_of(args):
    v = orc.find_vault(getattr(args, "vault", None))
    if not v:
        sys.exit("找不到研究库根目录（需要 Meta/ 和 01-Research-Projects/）；请在库根目录运行或加 --vault。")
    return v


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    orc.wjson(path, obj)


def read_text(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def relpath(path, vault):
    return os.path.relpath(path, vault).replace("\\", "/")


def in_vault(vault, path):
    return os.path.abspath(path if os.path.isabs(path) else os.path.join(vault, path))


def print_findings(errors, warns):
    for x in errors:
        print("错误  " + x)
    for x in warns:
        print("警告  " + x)


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_title(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (t or "").lower())).strip()


def similar(a, b):
    return difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def has_cjk(s):
    return any("一" <= ch <= "鿿" for ch in (s or ""))


def _year_int(v):
    m = re.search(r"\b(\d{4})\b", str(v or ""))
    return int(m.group(1)) if m else None


def _safe_stem(key):
    return re.sub(r"[^\w.\-]", "_", key)


def _note_file(vault, e):
    if e.get("note_path"):
        return in_vault(vault, e["note_path"])
    return os.path.join(vault, "03-Literature", _safe_stem(e["key"]) + ".md")


def _pdf_file(vault, e):
    if e.get("pdf"):
        return in_vault(vault, e["pdf"])
    return os.path.join(vault, "03-Literature", "_sources", _safe_stem(e["key"]) + ".pdf")


def _strip_frontmatter(text):
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join([""] * (i + 1) + lines[i + 1:])
    return text


# ------------------------------------------------------------------ Crossref
def offline(args=None):
    return bool(getattr(args, "offline", False)) or os.environ.get("ERC_OFFLINE") == "1"


def crossref_fetch(doi=None, title=None):
    """Return a list of candidate dicts {doi,title,year,venue,authors}. [] on any failure.
    ERC_CROSSREF_MOCK=<json file> replaces the network (tests)."""
    mock = os.environ.get("ERC_CROSSREF_MOCK")
    if mock:
        data = load(mock, {})
        return data.get("doi:" + (doi or "").lower(), []) if doi else data.get("title:" + norm_title(title), [])
    if doi:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    else:
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
            {"query.bibliographic": title, "rows": 3, "select": "DOI,title,issued,container-title,author"})
    req = urllib.request.Request(url, headers={"User-Agent": "EconomicsResearchCrew/1.0 (citation check)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    items = [payload["message"]] if doi else payload.get("message", {}).get("items", [])
    out = []
    for it in items:
        t = (it.get("title") or [""])[0]
        yr = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"doi": it.get("DOI"), "title": t, "year": yr,
                    "venue": (it.get("container-title") or [""])[0],
                    "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in it.get("author", [])]})
    return out


def verify_entry(e, off):
    """Update status/verified_by on entry e in place; returns the status."""
    manual = e.get("type") in ("chinese", "legal")
    if manual or off:
        if e.get("status") not in OK_STATUS:
            e["status"] = "manual" if manual else "unverified"
        return e["status"]
    cands = crossref_fetch(doi=e["doi"]) if e.get("doi") else crossref_fetch(title=e["title"])
    if not cands:
        e["status"] = "unverified"
        e["note_verify"] = "Crossref 没有返回结果（或网络不可用）"
        return e["status"]

    def year_ok_for(c):
        y1, y2 = _year_int(e.get("year")), _year_int(c.get("year"))
        return (y1 is None) or (y2 is None) or abs(y1 - y2) <= 1

    # the same title often has several records (working paper vs journal version): prefer one whose
    # title AND year both match; otherwise report the closest title
    viable = [c for c in cands if similar(c["title"], e["title"]) >= 0.9 and year_ok_for(c)]
    best = max(viable or cands, key=lambda c: similar(c["title"], e["title"]))
    ratio = similar(best["title"], e["title"])
    if ratio >= 0.9 and year_ok_for(best):
        e["status"], e["verified_by"] = "verified", "crossref"
        e["doi"] = e.get("doi") or best.get("doi")
        for fld in ("year", "venue", "authors"):
            if not e.get(fld) and best.get(fld):
                e[fld] = best[fld]
        e["note_verify"] = "标题相似度 %.2f" % ratio
    elif e.get("doi"):
        e["status"] = "mismatch"
        e["note_verify"] = "该 DOI 对应的标题是《%s》（%s），与登记标题不符" % (best["title"], best.get("year"))
    else:
        e["status"] = "unverified"
        e["note_verify"] = "最接近的结果《%s》（%s）相似度 %.2f，不足以确认" % (best["title"], best.get("year"), ratio)
    e["checked"] = now()
    return e["status"]


# ------------------------------------------------------------------ cite
def cmap(vault):
    path = os.path.join(vault, MAP_REL)
    return path, load(path, {"version": 1, "entries": {}})


def cmd_cite_add(a):
    vault = vault_of(a)
    path, m = cmap(vault)
    if not KEY_RE.match(a.key):
        sys.exit("key 只能含字母数字、下划线、冒号、连字符，且以字母开头：%s" % a.key)
    if a.key in m["entries"] and not a.replace:
        sys.exit("key 已存在：%s（要覆盖请加 --replace）" % a.key)
    e = {"key": a.key, "title": a.title, "authors": [x.strip() for x in (a.authors or "").split(";") if x.strip()],
         "year": a.year, "doi": (a.doi or "").strip() or None, "venue": a.venue or "", "type": a.type,
         "status": "unverified", "added": now()}
    for fld in ("locator", "claim_scope"):
        val = (getattr(a, fld, None) or "").strip()
        if val:
            e[fld] = val
    if a.type == "legal":
        if not (a.doc_no and a.effective):
            sys.exit("法规文件必须提供 --doc-no（文号）和 --effective（生效日期）。")
        e["doc_no"], e["effective"] = a.doc_no, a.effective
    st = verify_entry(e, offline(a))
    m["entries"][a.key] = e
    save(path, m)
    orc.ledger_append(vault, "cite_add", key=a.key, status=st)
    print("%s -> %s%s" % (a.key, st, "（%s）" % e["note_verify"] if e.get("note_verify") else ""))
    if st in ("manual", "unverified", "mismatch"):
        print("  需要人工核对后由研究者运行：paper_tools.py cite confirm --key %s --note \"…\"" % a.key)


def cmd_cite_verify(a):
    vault = vault_of(a)
    path, m = cmap(vault)
    keys = list(m["entries"]) if a.all or not a.key else [a.key]
    for k in keys:
        e = m["entries"].get(k)
        if not e:
            sys.exit("没有这个 key：%s" % k)
        if e.get("status") in OK_STATUS:
            continue
        st = verify_entry(e, offline(a))
        print("%-24s %s" % (k, st))
    save(path, m)


def cmd_cite_confirm(a):
    vault = vault_of(a)
    path, m = cmap(vault)
    e = m["entries"].get(a.key)
    if not e:
        sys.exit("没有这个 key：%s" % a.key)
    if not (a.note or "").strip():
        sys.exit("必须用 --note 写明研究者如何核对（例如：已在知网/官网核对原文，页码 …）。")
    e["status"], e["verified_by"], e["confirm_note"], e["checked"] = "confirmed", "researcher", a.note, now()
    save(path, m)
    orc.ledger_append(vault, "cite_confirm", key=a.key, note=a.note)
    print("%s 已由研究者确认。" % a.key)


def draft_keys(text):
    keys = []
    for grp in CITE_GROUP.findall(strip_code(text)):
        keys += CITE_KEY.findall(grp)
    return keys


def cite_problems(vault, files, strict, entries=None):
    """(errors, warnings, used_keys) for the given draft files."""
    if entries is None:
        _, m = cmap(vault)
        entries = m["entries"]
    errors, warns, used = [], [], set()
    for f in files:
        rel = relpath(f, vault)
        for k in draft_keys(read_text(f)):
            used.add(k)
            e = entries.get(k)
            if e is None:
                errors.append("%s：引用键 @%s 不在引文表中" % (rel, k))
            elif e.get("status") not in OK_STATUS:
                (errors if strict else warns).append("%s：@%s 状态为 %s（未核验）" % (rel, k, e.get("status")))
    return sorted(set(errors)), sorted(set(warns)), used


def cmd_cite_check(a):
    vault = vault_of(a)
    _, m = cmap(vault)
    errors, warns, used = cite_problems(vault, a.files, a.strict, m["entries"])
    print_findings(errors, warns)
    unused = sorted(set(m["entries"]) - used)
    if unused:
        print("提示  引文表中未被引用：" + ", ".join(unused))
    print("引用键 %d 个；错误 %d，警告 %d。" % (len(used), len(errors), len(warns)))
    sys.exit(1 if errors else 0)


def bibtex(e):
    typ = {"book": "book", "legal": "misc"}.get(e.get("type"), "article")
    f = [("title", e["title"]), ("author", " and ".join(e.get("authors", []))), ("year", e.get("year")),
         ("journal" if typ == "article" else "publisher", e.get("venue")), ("doi", e.get("doi")),
         ("url", e.get("url")), ("volume", e.get("volume")), ("number", e.get("issue")),
         ("pages", re.sub(r"-+", "--", e["pages"]) if e.get("pages") else None),
         ("abstract", e.get("abstract")), ("keywords", ", ".join(e.get("keywords", [])))]
    if e.get("type") == "legal":
        f.append(("note", "%s，%s 生效" % (e.get("doc_no"), e.get("effective"))))
    f.append(("note" if e.get("type") != "legal" else "annote", "核验状态：%s" % e.get("status")))
    body = ",\n".join("  %s = {%s}" % (k, v) for k, v in f if v)
    return "@%s{%s,\n%s\n}\n" % (typ, e["key"], body)


def cmd_cite_bib(a):
    vault = vault_of(a)
    _, m = cmap(vault)
    out = "\n".join(bibtex(e) for e in m["entries"].values())
    if a.output:
        with open(a.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        print("已写入 %s（%d 条）" % (a.output, len(m["entries"])))
    else:
        print(out)


def cmd_cite_list(a):
    vault = vault_of(a)
    _, m = cmap(vault)
    for k, e in sorted(m["entries"].items()):
        print("%-24s %-11s %s (%s)" % (k, e.get("status"), e.get("title", "")[:60], e.get("year")))
    print("共 %d 条。" % len(m["entries"]))


def cmd_cite_from_note(a):
    """Bridge one or more 03-Literature/*.md notes into Meta/citation-map.json via frontmatter."""
    import wiki_lint as wl  # same folder, standard library only
    vault = vault_of(a)
    path, m = cmap(vault)
    added = 0
    for raw in a.files:
        np = in_vault(vault, raw)
        if not os.path.isfile(np):
            sys.exit("找不到文献笔记：%s" % raw)
        fm, err = wl.parse_frontmatter(read_text(np))
        if err or not fm:
            sys.exit("文献笔记缺少有效 frontmatter：%s（%s）" % (raw, err or "无 frontmatter"))
        key = str(fm.get("cite_key") or "").strip()
        if not key:
            stem = os.path.splitext(os.path.basename(np))[0]
            if KEY_RE.match(stem):
                key = stem
            else:
                sys.exit("%s 缺少 frontmatter 字段 cite_key（且文件名不能直接作为英文 key）。" % raw)
        if not KEY_RE.match(key):
            sys.exit("cite_key 格式非法：%s（仅允许字母开头及字母数字下划线冒号连字符）" % key)
        if key in m["entries"] and not a.replace:
            print("%s -> 跳过（已存在；要更新请加 --replace）" % key)
            continue
        title = str(fm.get("title") or "").strip()
        if not title:
            sys.exit("%s 缺少 frontmatter 字段 title。" % raw)
        authors = fm.get("authors") or []
        if isinstance(authors, str):
            authors = [x.strip() for x in re.split(r"[;,]", authors) if x.strip()]
        year = str(fm.get("year") or "").strip() or None
        doi = str(fm.get("doi") or "").strip() or None
        venue = str(fm.get("journal") or fm.get("venue") or "").strip()
        ctype = str(fm.get("cite_type") or "").strip().lower()
        if ctype not in ("article", "book", "chinese", "legal"):
            ctype = "chinese" if has_cjk(title) else "article"
        e = {"key": key, "title": title, "authors": authors, "year": year, "doi": doi, "venue": venue,
             "type": ctype, "status": "unverified", "note_path": relpath(np, vault), "added": now()}
        for fld in ("locator", "claim_scope"):
            val = str(fm.get(fld) or "").strip()
            if val:
                e[fld] = val
        if ctype == "legal":
            doc_no = str(fm.get("doc_no") or "").strip()
            eff = str(fm.get("effective") or "").strip()
            if not (doc_no and eff):
                sys.exit("%s 为法规条目，frontmatter 需包含 doc_no 与 effective。" % raw)
            e["doc_no"], e["effective"] = doc_no, eff
        if str(fm.get("url") or "").strip():
            e["url"] = str(fm["url"]).strip()
        old = m["entries"].get(key)
        if old:  # keep bibliographic extras that a note's frontmatter does not carry (e.g. imported abstract)
            for fld in ("abstract", "keywords", "volume", "issue", "pages", "imported_from", "pdf", "sha256", "zotero_key"):
                if old.get(fld) and not e.get(fld):
                    e[fld] = old[fld]
        st = verify_entry(e, offline(a))
        m["entries"][key] = e
        orc.ledger_append(vault, "cite_add", key=key, status=st, from_note=e["note_path"])
        print("%s -> %s（来自 %s）" % (key, st, e["note_path"]))
        added += 1
    if added:
        save(path, m)
    print("共桥接登记 %d 条。" % added)


# ------------------------------------------------------------------ reference managers (EndNote / Zotero)
def _import_records(a, vault, path, m, recs, label, base_dir=None):
    import refmgr  # same folder, standard library only
    unverified_only = (not getattr(a, "verify", False)) or offline(a)
    taken = set(m["entries"])
    dup_index = refmgr.build_dup_index(m["entries"])
    pdf_index = refmgr.build_pdf_index(a.pdf_dir) if (a.attach and a.pdf_dir) else None
    tpl_path = os.path.join(vault, "Templates", "literature-note.md")
    template = read_text(tpl_path) if os.path.isfile(tpl_path) else ""
    tag = "[dry-run] " if a.dry_run else ""
    st_n = {"new": 0, "dup": 0, "skip": 0, "notes": 0, "pdf": 0}
    new_notes = []
    for rec in recs:
        title = rec.get("title") or ""
        if not title:
            print("%s跳过：缺少标题" % tag)
            st_n["skip"] += 1
            continue
        typ = refmgr.decide_type(rec)
        if typ is None:
            print("%s跳过《%s》：法规类条目需要文号与生效日期，请用 cite add --type legal 手动登记" % (tag, title[:30]))
            st_n["skip"] += 1
            continue
        dup = refmgr.find_duplicate(rec, m["entries"], dup_index)
        if dup and not a.replace:
            print("%s%s -> 跳过（与已有条目 %s 重复；要覆盖请加 --replace）" % (tag, title[:30], dup))
            st_n["dup"] += 1
            continue
        key = dup or refmgr.make_key(rec, taken)
        e = refmgr.to_entry(rec, key, typ, now(), label)
        if dup:
            old = m["entries"][dup]
            e["added"] = old.get("added", e["added"])
            for fld in ("note_path", "locator", "claim_scope", "pdf", "sha256", "zotero_key"):
                if old.get(fld) and not e.get(fld):
                    e[fld] = old[fld]
        st = verify_entry(e, unverified_only)
        src_rel = sha = None
        if a.attach:
            pdf = refmgr.resolve_pdf(rec.get("files", []), base_dir, a.pdf_dir, pdf_index)
            if pdf and a.dry_run:
                src_rel = "(将复制 %s)" % os.path.basename(pdf)
            elif pdf:
                src_rel, sha, how = refmgr.attach_pdf(vault, key, pdf)
                if how == "conflict":
                    print("警告  %s：03-Literature/_sources 里已有内容不同的同名 PDF，未复制" % key)
                    src_rel = sha = None
                else:
                    e["pdf"], e["sha256"] = src_rel, sha
                    st_n["pdf"] += 1
            elif rec.get("files"):
                print("提示  %s：找不到 PDF 文件（可用 --pdf-dir 指向 EndNote 的 .Data/PDF 或 Zotero 的 storage 目录）" % key)
        if not a.no_notes and not e.get("note_path"):
            rel = refmgr.note_rel(key)
            np = os.path.join(vault, rel)
            if os.path.exists(np):
                print("提示  笔记已存在，未改动：%s" % rel)
            else:
                e["note_path"] = rel
                if not a.dry_run:
                    os.makedirs(os.path.dirname(np), exist_ok=True)
                    with open(np, "w", encoding="utf-8", newline="\n") as fh:
                        fh.write(refmgr.note_text(e, template, src_rel, sha, now()[:10]))
                st_n["notes"] += 1
                new_notes.append((key, os.path.splitext(os.path.basename(rel))[0], title, 1 if (src_rel and sha) else 0))
        m["entries"][key] = e
        taken.add(key)
        refmgr.index_entry(dup_index, key, e)
        st_n["new"] += 1
        if not a.dry_run:
            orc.ledger_append(vault, "cite_add", key=key, status=st, from_import=label)
        print("%s%s -> %s（%s%s）" % (tag, key, st, typ, "，已覆盖" if dup else ""))
    if st_n["new"] and not a.dry_run:
        save(path, m)
        if new_notes:
            _index_and_log(vault, label, new_notes, st_n)
    print("%s导入 %d 条（跳过重复 %d、无效 %d）；新建文献笔记 %d 篇；复制 PDF %d 个。" % (
        tag, st_n["new"], st_n["dup"], st_n["skip"], st_n["notes"], st_n["pdf"]))
    if st_n["new"]:
        print("  导入的条目一律为 unverified/manual；核对后用 cite verify 或由研究者 cite confirm，写稿前不要直接引用。")


def _write_keep_eol(path, text):
    with open(path, "rb") as fh:
        crlf = b"\r\n" in fh.read()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", "\r\n") if crlf else text)


def _index_and_log(vault, label, notes, st_n):
    """Register new literature notes in Meta/index.md (文献 table) and append a Meta/log.md entry,
    the same ledger bookkeeping /ingest-source does, so lint does not flag the imported notes."""
    today = now()[:10]
    ip = os.path.join(vault, "Meta", "index.md")
    if os.path.isfile(ip):
        text = read_text(ip)
        lines = text.split("\n")
        rows = ["| [[%s]] | %s（导入，未核实） | %s | %d | %s |" % (stem, t.replace("|", "/")[:60], k, n, today)
                for k, stem, t, n in notes if "[[%s]]" % stem not in text]
        h = next((i for i, ln in enumerate(lines) if ln.startswith("### 文献")), None)
        if rows and h is not None:
            j = h + 1
            while j < len(lines) and not lines[j].startswith(("|", "#")):
                j += 1
            if j < len(lines) and lines[j].startswith("|"):
                while j < len(lines) and lines[j].startswith("|"):
                    j += 1
                lines[j:j] = rows
                _write_keep_eol(ip, "\n".join(lines))
            else:
                print("提示  Meta/index.md 的“文献”表格不完整，未登记；请由 /ingest-source 或 /wiki-lint 补登。")
    lp = os.path.join(vault, "Meta", "log.md")
    if os.path.isfile(lp):
        text = read_text(lp)
        entry = ("\n## [%s] ingest | 参考文献软件导入（%s）\n- 项目 / 页面：03-Literature/（新建 %d 篇文献笔记，均为 unverified）\n"
                 "- Agent / Skill：paper_tools.py cite import\n- 输入：%s\n- 输出：citation-map.json 新增 %d 条；复制 PDF %d 个\n"
                 "- 核验：全部 unverified / manual；核对原文后运行 cite verify，或由研究者 cite confirm\n- 研究者决定：\n") % (
            today, label, st_n["notes"], label, st_n["new"], st_n["pdf"])
        _write_keep_eol(lp, text.rstrip("\n") + "\n" + entry)
    print("  已登记到 Meta/index.md 与 Meta/log.md；建议运行 python .claude/scripts/wiki_lint.py map --vault . 刷新地图。")


def cmd_cite_import(a):
    import refmgr
    vault = vault_of(a)
    path, m = cmap(vault)
    for raw in a.files:
        fp = raw if os.path.isfile(raw) else in_vault(vault, raw)
        if not os.path.isfile(fp):
            sys.exit("找不到文件：%s" % raw)
        with open(fp, "rb") as fh:
            text = refmgr.decode_bytes(fh.read())
        try:
            fmt = refmgr.detect_format(fp, text) if a.format == "auto" else a.format
            recs = refmgr.parse_text(fmt, text)
        except (refmgr.RefError, ValueError) as ex:
            sys.exit("%s 解析失败：%s" % (raw, ex))
        print("%s：%s，%d 条记录" % (os.path.basename(fp), fmt, len(recs)))
        _import_records(a, vault, path, m, recs, "%s:%s" % (fmt, os.path.basename(fp)), os.path.dirname(os.path.abspath(fp)))


def _znote_html(vault, e):
    import html as _h
    p = _note_file(vault, e)
    if not os.path.isfile(p):
        sys.exit("没有文献笔记 %s，无可回写内容。" % relpath(p, vault))
    text = re.sub(r"<!--.*?-->", "", read_text(p), flags=re.S)
    text = re.sub(r"^---\n.*?\n---\n", "", text.replace("\r\n", "\n"), count=1, flags=re.S)
    parts, head, body = [], None, []
    def flush():
        t = "\n".join(body).strip()
        if head and t and not t.startswith("导入信息"):
            parts.append((head, t))
    for ln in text.split("\n"):
        if ln.startswith("#"):
            flush(); head, body = ln.lstrip("# ").strip(), []
        else:
            body.append(ln)
    flush()
    parts = [(h, t) for h, t in parts if h != "导入信息"]
    if not parts:
        sys.exit("文献笔记还没有实质内容（各节为空），先填写再回写。")
    out = ["<p><b>ERC 文献笔记</b> · cite_key: %s · 核验状态: %s</p>" % (_h.escape(e["key"]), _h.escape(e.get("status", "")))]
    for h, t in parts:
        out.append("<h2>%s</h2><p>%s</p>" % (_h.escape(h), _h.escape(t).replace("\n", "<br/>")))
    out.append("<p><small>erc:cite_key=%s</small></p>" % _h.escape(e["key"]))
    return "".join(out)[:20000]


def _zotero_base(a):
    if a.base_url:
        return a.base_url, "zotero:custom"
    if a.user:
        return "https://api.zotero.org/users/%s" % a.user, "zotero:user/%s" % a.user
    if a.group:
        return "https://api.zotero.org/groups/%s" % a.group, "zotero:group/%s" % a.group
    return "http://127.0.0.1:23119/api/users/0", "zotero:local"


def cmd_cite_zotero(a):
    import refmgr
    vault = vault_of(a)
    path, m = cmap(vault)
    base, label = _zotero_base(a)
    key = os.environ.get("ZOTERO_API_KEY")
    try:
        refmgr.check_base(base, offline(a))
        if a.item:
            items = refmgr.zotero_one(base, key, a.item)
        elif a.query:
            items = refmgr.zotero_search(base, key, a.query, a.limit)
        else:
            items = refmgr.zotero_fetch(base, key, a.collection, a.limit)
        recs = refmgr.parse_csl(json.dumps(items))
    except (refmgr.RefError, ValueError) as ex:
        sys.exit(str(ex))
    print("从 Zotero 取得 %d 条（只发出 GET 请求，未上传任何库内内容）；该方式只含元数据，PDF 请用 BibTeX/RIS 导出配合 --attach。" % len(items))
    for it in items[:20] if a.query and a.list else []:
        print("  [%s] %s (%s)" % (it.get("id", ""), it.get("title", ""), ((it.get("issued") or {}).get("date-parts") or [[""]])[0][0]))
    if a.query and a.list:
        return
    _import_records(a, vault, path, m, recs, label, None)
    if a.notes and not a.dry_run:
        ids = {str(it.get("id")) for it in items}
        _, m2 = cmap(vault)
        added = 0
        for e in m2["entries"].values():
            zk = e.get("zotero_key")
            if not zk or zk not in ids:
                continue
            np_ = _note_file(vault, e)
            if not os.path.isfile(np_) or "## Zotero 笔记" in read_text(np_):
                continue
            try:
                notes = [refmgr.html_to_text(h) for h in refmgr.zotero_notes(base, key, zk) if "erc:cite_key=" not in h]
            except refmgr.RefError as ex:
                print("提示  %s 的 Zotero 笔记未取得：%s" % (e["key"], ex)); continue
            if notes:
                body = "\n\n## Zotero 笔记（只读来源，导入于 %s）\n\n" % now()[:10] + "\n\n".join("> " + n.replace("\n", "\n> ") for n in notes) + "\n"
                _write_keep_eol(np_, read_text(np_).rstrip("\n") + body)
                added += 1
        print("已把 %d 篇文献的 Zotero 笔记追加到对应文献笔记。" % added)


def cmd_cite_open(a):
    vault = vault_of(a)
    _, m = cmap(vault)
    e = m["entries"].get(a.key)
    if e is None:
        sys.exit("引文表中没有 %s" % a.key)
    pdf = _pdf_file(vault, e)
    if not os.path.isfile(pdf):
        sys.exit("没有 %s；先用 cite import --attach（或 --pdf-dir）把 PDF 复制进 _sources。" % pdf)
    print(pdf)
    if a.print:
        return
    import subprocess
    if hasattr(os, "startfile"):
        os.startfile(pdf)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", pdf])


def cmd_cite_zotero_note(a):
    import refmgr
    vault = vault_of(a)
    _, m = cmap(vault)
    e = m["entries"].get(a.key) or sys.exit("引文表中没有 %s" % a.key)
    zk = a.zotero_key or e.get("zotero_key") or sys.exit("缺少 Zotero 条目 key：用 --zotero-key 指定（从 Zotero 拉取导入的条目已自动记录）。")
    html_note = _znote_html(vault, e)
    base, _ = _zotero_base(a)
    print("将在 Zotero 条目 %s 下新建一条子笔记（%d 字符，只新增，不改动或删除任何已有条目）：" % (zk, len(html_note)))
    print(refmgr.html_to_text(html_note)[:600])
    if not a.yes:
        print("\n[dry-run] 未写入。确认无误后加 --yes（需 ZOTERO_API_KEY，且为有写权限的密钥）。")
        return
    try:
        refmgr.check_base(base, offline(a))
        key = os.environ.get("ZOTERO_API_KEY")
        if any("erc:cite_key=%s" % a.key in h for h in refmgr.zotero_notes(base, key, zk)):
            print("Zotero 中已有该文献的 ERC 笔记，跳过（避免重复）。"); return
        refmgr.zotero_post_note(base, key, zk, html_note)
    except refmgr.RefError as ex:
        sys.exit(str(ex))
    print("已写入 Zotero（标签 erc-exported）。")


def _export_table(a, render, enc="utf-8"):
    vault = vault_of(a)
    _, m = cmap(vault)
    out = render(list(m["entries"].values()))
    if a.output:
        with open(a.output, "w", encoding=enc, newline="\n") as fh:
            fh.write(out)
        print("已写入 %s（%d 条）" % (a.output, len(m["entries"])))
    else:
        print(out)


def cmd_cite_ris(a):
    import refmgr
    # BOM so that EndNote on Chinese Windows reads the file as Unicode
    _export_table(a, lambda es: "\n".join(refmgr.to_ris(e) for e in es), "utf-8-sig")


def cmd_cite_csl(a):
    import refmgr
    _export_table(a, lambda es: json.dumps([refmgr.to_csl(e) for e in es], ensure_ascii=False, indent=2) + "\n")


# ------------------------------------------------------------------ results
def rmap(vault):
    path = os.path.join(vault, RES_REL)
    return path, load(path, {"version": 1, "entries": {}})


def to_float(s):
    try:
        return float(str(s).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def register(vault, m, rid, value, label="", se=None, n=None, source=None, script=None, note="", no_source_reason=None):
    if not re.match(r"^[A-Za-z0-9_.\-:]+$", rid):
        sys.exit("id 只能含字母数字、下划线、点、冒号、连字符：%s" % rid)
    if source and no_source_reason:
        sys.exit("不能同时提供 --source 和 --no-source-reason；有源文件只填 --source，确无源文件才填诚实理由。")
    e = {"id": rid, "value": str(value), "numeric": to_float(value), "label": label, "se": se, "n": n,
         "note": note, "registered": now()}
    if no_source_reason:
        e["source"] = None
        e["no_source_reason"] = no_source_reason.strip()
    for fld, p in (("source", source), ("script", script)):
        if p:
            ap = in_vault(vault, p)
            if not orc.inside(ap, vault) or not os.path.isfile(ap):
                sys.exit("%s 必须是库内已存在的文件：%s" % (fld, p))
            e[fld] = relpath(ap, vault)
            if fld == "source":
                e["source_sha256"] = sha256(ap)
    m["entries"][rid] = e


def cmd_results_register(a):
    vault = vault_of(a)
    path, m = rmap(vault)
    if a.id in m["entries"] and not a.replace:
        sys.exit("id 已存在：%s（要覆盖请加 --replace）" % a.id)
    register(vault, m, a.id, a.value, a.label, a.se, a.n, a.source, a.script, a.note or "", a.no_source_reason)
    save(path, m)
    orc.ledger_append(vault, "result_register", id=a.id)
    e = m["entries"][a.id]
    if e.get("no_source_reason"):
        suffix = "  （诚实空值：%s）" % e["no_source_reason"]
    elif e.get("source"):
        suffix = ""
    else:
        suffix = "  （警告：没有 --source，无法追溯来源；若确无库内源文件请用 --no-source-reason 说明）"
    print("%s = %s%s" % (a.id, e["value"], suffix))


def _ascii_slug(s, fallback):
    slug = re.sub(r"[^A-Za-z0-9\-]+", "_", (s or "").strip()).strip("_")
    if slug:
        return slug
    return "%s_%s" % (fallback, hashlib.sha1((s or "").encode("utf-8")).hexdigest()[:6])


def cmd_results_import(a):
    vault = vault_of(a)
    path, m = rmap(vault)
    csv_path = in_vault(vault, a.csv)
    if not os.path.isfile(csv_path):
        sys.exit("找不到 %s" % a.csv)
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        sys.exit("CSV 至少需要表头和一行数据。")
    header, count, seen_ids = rows[0], 0, set()
    for ri, r in enumerate(rows[1:], 1):
        if not r or not r[0].strip():
            continue
        rowkey = _ascii_slug(r[0], "r%d" % ri)
        for j in range(1, min(len(header), len(r))):
            if r[j].strip() == "":
                continue
            colkey = _ascii_slug(header[j], "c%d" % j)
            base_id = "%s.%s.%s" % (a.prefix, rowkey, colkey)
            rid, suffix = base_id, 2
            while rid in seen_ids:
                rid = "%s_%d" % (base_id, suffix)
                suffix += 1
            seen_ids.add(rid)
            register(vault, m, rid, r[j].strip(), "%s / %s / %s" % (a.prefix, r[0].strip(), header[j].strip()),
                     source=a.source or os.path.relpath(csv_path, vault), script=a.script)
            count += 1
    save(path, m)
    orc.ledger_append(vault, "result_import", prefix=a.prefix, count=count)
    print("已登记 %d 个数值（前缀 %s）。" % (count, a.prefix))


def render_text(text, m):
    missing = []

    def sub(mo):
        e = m["entries"].get(mo.group(1))
        if e is None:
            missing.append(mo.group(1))
            return mo.group(0)
        val = e["value"]
        if mo.group(2) is not None and e.get("numeric") is not None:
            val = ("%." + mo.group(2) + "f") % e["numeric"]
        return val
    return PLACEHOLDER.sub(sub, text), missing


def cmd_results_render(a):
    vault = vault_of(a)
    _, m = rmap(vault)
    out, missing = render_text(read_text(a.draft), m)
    if missing:
        sys.exit("以下 id 不在结果登记簿中，未渲染：" + ", ".join(sorted(set(missing))))
    target = a.output or (re.sub(r"\.md$", ".rendered.md", a.draft, flags=re.I)
                          if a.draft.lower().endswith(".md") else a.draft + ".rendered")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("已写入 %s" % target)


def bare_stats(text):
    t = _strip_frontmatter(strip_code(text))
    t = PLACEHOLDER.sub(" ", t)
    t = CITE_GROUP.sub(" ", t)
    t = re.sub(r"https?://\S+|\b(?:19|20)\d{2}\b", " ", t)
    hits = []
    for i, line in enumerate(t.split("\n"), 1):
        if line.lstrip().startswith("#"):
            continue
        for mo in STAT_RE.finditer(line):
            if mo.group(1).replace(" ", "") not in SAFE_DECIMALS:
                hits.append((i, mo.group(1)))
    return hits


def results_problems(vault, files):
    _, m = rmap(vault)
    errors, warns, sha_cache = [], [], {}
    for f in files:
        text, rel = read_text(f), relpath(f, vault)
        for mo in PLACEHOLDER.finditer(strip_code(text)):
            e = m["entries"].get(mo.group(1))
            if e is None:
                errors.append("%s：{{res:%s}} 不在结果登记簿中" % (rel, mo.group(1)))
            elif e.get("source"):
                sp = os.path.join(vault, e["source"])
                if sp not in sha_cache:
                    sha_cache[sp] = sha256(sp) if os.path.isfile(sp) else None
                if sha_cache[sp] != e.get("source_sha256"):
                    warns.append("%s：%s 的来源文件 %s 已变化或缺失，登记值可能过期" % (rel, mo.group(1), e["source"]))
        bs = bare_stats(text)
        if bs:
            warns.append("%s：有 %d 处统计量没有链接到结果登记簿（例如第 %d 行的 %s）" % (rel, len(bs), bs[0][0], bs[0][1]))
    return sorted(set(errors)), sorted(set(warns))


def cmd_results_check(a):
    vault = vault_of(a)
    errors, warns = results_problems(vault, a.files)
    print_findings(errors, warns)
    print("错误 %d，警告 %d。" % (len(errors), len(warns)))
    sys.exit(1 if errors else 0)


# ------------------------------------------------------------------ questions
def open_questions(text):
    t = strip_code(text)
    out = []
    for mo in Q_RE.finditer(t):
        if not re.match(r"\s*⟦答：", t[mo.end():mo.end() + 12]):
            out.append(mo.group(1).strip())
    return out


def cmd_questions(a):
    vault = vault_of(a)
    total = 0
    for f in a.files:
        for q in open_questions(read_text(f)):
            total += 1
            print("%s：⟦问：%s⟧" % (relpath(f, vault), q))
    print("未回答 %d 个。" % total)
    sys.exit(1 if total else 0)


# ------------------------------------------------------------------ refine
def paper_dir(args, vault):
    proj = getattr(args, "project", None)
    if proj:
        pdir = os.path.join(vault, orc.PROJECTS_DIR, proj)
    else:
        ap = orc.active_project(vault)
        if not ap:
            sys.exit("没有进行中的项目；用 --project <项目目录名> 指定。")
        pdir = os.path.dirname(ap[0])
    return os.path.join(pdir, "paper")


def parse_scores(s):
    out = {}
    for part in (s or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                sys.exit("评分必须是数字：%s" % part)
    return out


def decide(prev, cur):
    """Accept a revision only if Fatal did not increase AND either Major strictly decreased, or Major is equal
    and the total score (same dimensions in both reviews) is not lower. Revert when the scored dimensions differ
    (not comparable) or any dimension dropped by 2 or more points."""
    if cur["fatal"] > prev["fatal"]:
        return "revert", "Fatal 数增加（%d → %d）" % (prev["fatal"], cur["fatal"])
    if set(prev["scores"]) != set(cur["scores"]):
        diff = sorted(set(prev["scores"]) ^ set(cur["scores"]))
        return "revert", "两次评审的评分维度不一致，无法比较：" + ", ".join(diff)
    drops = [k for k in prev["scores"] if prev["scores"][k] - cur["scores"][k] >= 2]
    if drops:
        return "revert", "维度分下降 ≥2：" + ", ".join(drops)
    if cur["major"] < prev["major"]:
        return "accept", "Fatal 未增加，Major 减少（%d → %d）" % (prev["major"], cur["major"])
    if cur["major"] == prev["major"] and cur["scores"] and sum(cur["scores"].values()) >= sum(prev["scores"].values()):
        return "accept", "Fatal 与 Major 未增加，总分不低于上一采用版"
    return "revert", "没有可确认的改进（Fatal %d → %d，Major %d → %d）" % (prev["fatal"], cur["fatal"], prev["major"], cur["major"])


def cmd_refine_start(a):
    vault = vault_of(a)
    pd = paper_dir(a, vault)
    src = os.path.abspath(a.draft)
    if not os.path.isfile(src):
        sys.exit("找不到 %s" % a.draft)
    v0 = os.path.join(pd, "versions", "v0.md")
    if os.path.exists(v0):
        sys.exit("v0 已存在：%s" % v0)
    os.makedirs(os.path.dirname(v0), exist_ok=True)
    with open(src, "rb") as fi, open(v0, "wb") as fo:
        fo.write(fi.read())
    save(os.path.join(pd, "reviews.json"), {"max_rounds": MAX_ROUNDS, "current": "v0", "rounds": []})
    orc.ledger_append(vault, "refine_start", draft=relpath(src, vault))
    print("已保存 %s。先对 v0 做一次独立评审，再用 refine record --version v0 登记基线。" % os.path.relpath(v0, vault))


def cmd_refine_record(a):
    vault = vault_of(a)
    pd = paper_dir(a, vault)
    rp = os.path.join(pd, "reviews.json")
    st = load(rp, None)
    if st is None:
        sys.exit("先运行 refine start。")
    ver = re.sub(r"\.md$", "", os.path.basename(a.version))
    if not os.path.isfile(os.path.join(pd, "versions", ver + ".md")):
        sys.exit("找不到 versions/%s.md" % ver)
    if any(r["version"] == ver for r in st["rounds"]):
        sys.exit("%s 已登记过评审。" % ver)
    # Two ways to report counts. Direct (--fatal/--major): a fresh independent count. Checklist
    # (--carried-* / --new-*): the reviewer re-checks the baseline's numbered issues and lists new ones, so
    # the counts are comparable across rounds even when a different reviewer instance does the re-review.
    direct = a.fatal is not None or a.major is not None
    checklist = any(x is not None for x in (a.carried_fatal, a.carried_major, a.new_fatal, a.new_major))
    if direct and checklist:
        sys.exit("直接计数（--fatal/--major）与清单计数（--carried-*/--new-*）只能二选一。")
    if direct:
        if a.fatal is None or a.major is None:
            sys.exit("直接计数需要同时给出 --fatal 和 --major。")
        if st["rounds"]:
            sys.exit("复评必须按基线清单复核：请用 --carried-fatal/--carried-major（可加 --new-*），直接计数只用于基线。")
    elif checklist:
        if a.carried_fatal is None or a.carried_major is None:
            sys.exit("清单计数需要同时给出 --carried-fatal 和 --carried-major（可加 --new-fatal / --new-major）。")
        if not st["rounds"]:
            sys.exit("基线没有可复核的上一轮清单，请用 --fatal/--major 直接计数。")
    else:
        sys.exit("给出 --fatal 和 --major，或给出 --carried-fatal 和 --carried-major（可加 --new-fatal / --new-major）。")
    for name, val in (("fatal", a.fatal), ("major", a.major), ("minor", a.minor), ("carried-fatal", a.carried_fatal),
                      ("carried-major", a.carried_major), ("new-fatal", a.new_fatal), ("new-major", a.new_major)):
        if val is not None and val < 0:
            sys.exit("--%s 不能为负数：%d" % (name, val))
    base = next((r for r in st["rounds"] if r["version"] == st["current"]), None)
    if checklist:
        if a.carried_fatal > base["fatal"] or a.carried_major > base["major"]:
            sys.exit("carried 不能超过基线（%s）的条数：Fatal %d、Major %d。" % (base["version"], base["fatal"], base["major"]))
        a.fatal = a.carried_fatal + (a.new_fatal or 0)
        a.major = a.carried_major + (a.new_major or 0)
    rec = {"version": ver, "fatal": a.fatal, "major": a.major, "minor": a.minor, "scores": parse_scores(a.scores),
           "method": "checklist" if checklist else "direct", "note": a.note or "", "ts": now()}
    if checklist:
        rec["carried"] = {"fatal": a.carried_fatal, "major": a.carried_major}
        rec["new"] = {"fatal": a.new_fatal or 0, "major": a.new_major or 0}
    if not st["rounds"]:
        rec["decision"], rec["reason"] = "baseline", "基线"
        st["current"] = ver
    else:
        rounds_done = len(st["rounds"]) - 1
        if rounds_done >= st["max_rounds"]:
            sys.exit("已达最多 %d 轮精修；交研究者在 C4 检查点决定。" % st["max_rounds"])
        rec["decision"], rec["reason"] = decide(base, rec)
        if rec["decision"] == "accept":
            st["current"] = ver
    st["rounds"].append(rec)
    save(rp, st)
    orc.ledger_append(vault, "refine_record", version=ver, decision=rec["decision"], fatal=a.fatal, major=a.major)
    left = st["max_rounds"] - (len(st["rounds"]) - 1)
    print("%s：%s（%s）。当前采用版本：%s；还剩 %d 轮。" % (ver, rec["decision"], rec["reason"], st["current"], max(left, 0)))
    if rec["decision"] == "revert":
        print("请回退到 %s，不要在被回退的版本上继续改。" % st["current"])


def cmd_refine_status(a):
    vault = vault_of(a)
    st = load(os.path.join(paper_dir(a, vault), "reviews.json"), None)
    if not st:
        sys.exit("没有精修记录。")
    print("当前采用：%s  已精修 %d/%d 轮" % (st["current"], max(len(st["rounds"]) - 1, 0), st["max_rounds"]))
    for r in st["rounds"]:
        print("  %-4s %-9s Fatal %d Major %d Minor %d  %s" % (r["version"], r["decision"], r["fatal"], r["major"], r["minor"], r["reason"]))


# ------------------------------------------------------------------ stage checks (used by orchestrator.verify)
CLAIM_TAG_RE = re.compile(r"<!--\s*claim:\s*([A-Za-z0-9_-]+)\s*-->")
OUTLINE_CLAIM_ROW_RE = re.compile(r"^\|\s*(C[A-Za-z0-9_-]+)\s*\|([^\n]+)", re.M)
CAUSAL_VERB_RE = re.compile(r"(导致|致使|引起|显著提高|显著降低|显著促进|显著抑制|因果效应|\bcauses?\b|\binduces?\b|\bdrives?\b)", re.I)


def claim_limited_to_association(rest):
    """Outline row after the id: | claim | type | estimand | evidence | allowed wording | limits |.
    Limited when the type cell says association/speculation, or the allowed-wording cell restricts causal verbs."""
    cells = [c.strip() for c in rest.split("|")]
    typ = cells[1] if len(cells) > 1 else ""
    wording = cells[4] if len(cells) > 4 else ""
    return (any(w in typ for w in ("相关", "关联", "描述"))
            or any(w in wording for w in ("相关", "关联", "仅描述", "推测", "一致", "探索性", "假说")))


def find_outline(vault, files, project):
    """outline.md of the project's paper/ folder, else next to the first draft file, else None."""
    candidates = []
    try:
        candidates.append(os.path.join(paper_dir(argparse.Namespace(project=project), vault), "outline.md"))
    except SystemExit:
        pass
    if files:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(files[0])), "outline.md"))
    return next((c for c in candidates if os.path.isfile(c)), None)


def claim_problems(vault, files, strict=False, project=None):
    """L3 claim-source alignment checks: anchorless citations, untagged result blocks, and causal overstatement."""
    _, cm = cmap(vault)
    errors, warns = [], []
    op = find_outline(vault, files, project)
    outline_claims = dict(OUTLINE_CLAIM_ROW_RE.findall(read_text(op))) if op else {}

    seen_claims = set()
    checked_non_outline = False
    for f in files:
        rel = relpath(f, vault)
        if os.path.basename(f).lower() != "outline.md":
            checked_non_outline = True
        txt = strip_code(read_text(f))
        for k in draft_keys(txt):
            e = cm["entries"].get(k)
            if e is not None and not e.get("locator"):
                (errors if strict else warns).append("%s：@%s 缺少定位锚点 locator（L3 anchorless 风险）" % (rel, k))
        pending_claims = []
        for para in re.split(r"\r?\n\s*\r?\n", txt):
            cids = CLAIM_TAG_RE.findall(para)
            if cids and not CLAIM_TAG_RE.sub("", para).strip():
                pending_claims.extend(cids)
                seen_claims.update(cids)
                continue
            eff_cids = pending_claims + cids
            pending_claims = []
            seen_claims.update(eff_cids)
            if PLACEHOLDER.search(para) and not eff_cids:
                warns.append("%s：含 {{res:...}} 的段落缺少 <!-- claim: Cn --> 标注" % rel)
            for cid in eff_cids:
                if outline_claims and cid not in outline_claims:
                    errors.append("%s：主张 %s 未在 outline.md 主张清单中定义" % (rel, cid))
                elif cid in outline_claims:
                    if claim_limited_to_association(outline_claims[cid]) and CAUSAL_VERB_RE.search(para):
                        (errors if strict else warns).append("%s：%s 在大纲中限定为相关/关联，但正文疑似使用强因果动词（OVERSTATED）" % (rel, cid))
        for cid in pending_claims:
            if outline_claims and cid not in outline_claims:
                errors.append("%s：主张 %s 未在 outline.md 主张清单中定义" % (rel, cid))
    if outline_claims and checked_non_outline:
        for cid in sorted(outline_claims):
            if cid not in seen_claims:
                warns.append("大纲主张 %s 尚未在正文通过 <!-- claim: %s --> 落地（请核对是否遗漏）" % (cid, cid))
    return sorted(set(errors)), sorted(set(warns))


def cmd_claim_check(a):
    vault = vault_of(a)
    errors, warns = claim_problems(vault, a.files, a.strict, getattr(a, "project", None))
    print_findings(errors, warns)
    print("主张审计：错误 %d，警告 %d。" % (len(errors), len(warns)))
    sys.exit(1 if errors else 0)


# ------------------------------------------------------------------ language polish: scan for AI tells, check invariants
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
EVIDENCE_RE = re.compile(r"\d|\{\{res:|表\s*[\dA-Za-z]|图\s*[\dA-Za-z]|\bTable\b|\bFigure\b")
CITE_EVIDENCE_RE = re.compile(r"\[[^\[\]]*@")
SENT_SPLIT = re.compile(r"(?<=[。！？!?])|(?<=[.])\s+(?=[A-Z\[])")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")
HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.M)


def load_tells(vault):
    path = os.path.join(vault, "Meta", "ai-tells.json")
    if not os.path.isfile(path):
        sys.exit("找不到 %s；请先安装或从包里复制 Meta/ai-tells.json。" % path)
    cfg = json.loads(read_text(path))
    rules = []
    for r in cfg.get("rules", []):
        try:
            rules.append(dict(r, _re=re.compile(r["regex"])))
        except (re.error, KeyError) as e:
            sys.exit("ai-tells.json 规则 %s 无效：%s" % (r.get("id", "?"), e))
    return cfg, rules


def is_zh(s):
    cjk = sum(1 for ch in s if "一" <= ch <= "鿿")
    return cjk >= max(4, 0.2 * len(s))


def prose_paragraphs(text):
    """Yield (first_line_no, paragraph_text) for prose only: no code, comments, headings, tables, front matter."""
    text = HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), strip_code(text))
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = [""] * (i + 1) + lines[i + 1:]
                break
    buf, start = [], 0
    for no, ln in enumerate(lines, 1):
        if not ln.strip() or ln.lstrip().startswith(("#", "|", ">", "```")):
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if not buf:
            start = no
        buf.append(ln.strip())
    if buf:
        yield start, " ".join(buf)


def scan_text(text, cfg, rules):
    hits = []
    max_zh, max_en = cfg.get("max_sentence_chars_zh", 90), cfg.get("max_sentence_words_en", 40)
    connectives = tuple(cfg.get("connective_starts_zh", []) + cfg.get("connective_starts_en", []))
    for line_no, para in prose_paragraphs(text):
        sents = [s.strip() for s in SENT_SPLIT.split(para) if s.strip()]
        seq = [s for s in sents if s.startswith(connectives)]
        if len(seq) >= cfg.get("connective_threshold", 3):
            hits.append((line_no, "连接词过度", seq[0][:12], "同一段多句以连接词开头；让逻辑承担连接，合并或删去"))
        for s in sents:
            zh = is_zh(s)
            for r in rules:
                lang = r.get("lang", "any")
                if (lang == "zh" and not zh) or (lang == "en" and zh):
                    continue
                m = r["_re"].search(s)
                if not m:
                    continue
                need = r.get("needs_evidence")
                if need and (CITE_EVIDENCE_RE if need == "cite" else EVIDENCE_RE).search(s):
                    continue
                hits.append((line_no, r.get("category", r["id"]), m.group(0), r.get("hint", "")))
            keys = sum(len(CITE_KEY.findall(g)) for g in CITE_GROUP.findall(s))
            if keys >= cfg.get("cite_dump_threshold", 4):
                hits.append((line_no, "文献堆砌", "%d 个引用" % keys, "只留最相关的 1–2 篇并说明相关在哪里"))
            clean_s = CITE_GROUP.sub("", PLACEHOLDER.sub("0", s)).strip()
            n = len(clean_s) if zh else len(clean_s.split())
            if n > (max_zh if zh else max_en):
                hits.append((line_no, "超长句", "%d %s" % (n, "字" if zh else "词"), "拆成一句一个意思，删去不承载信息的从句"))
    return sorted(hits, key=lambda h: (h[0], h[1]))


def cmd_polish_scan(a):
    vault = vault_of(a)
    cfg, rules = load_tells(vault)
    total, by_cat = 0, Counter()
    for f in a.files:
        hits = scan_text(read_text(f), cfg, rules)
        rel = relpath(f, vault)
        for line_no, cat, matched, hint in hits:
            print("%s:%d [%s] 「%s」 %s" % (rel, line_no, cat, matched, hint))
            by_cat[cat] += 1
        total += len(hits)
    print("命中 %d 处（%s）。仅作提示：先判断是否真是套话或夸大，再改；数字、引文、占位符与标记一律不改。" % (
        total, "、".join("%s %d" % kv for kv in sorted(by_cat.items())) or "无"))
    sys.exit(1 if (a.strict and total) else 0)


def polish_signature(text):
    body = _strip_frontmatter(strip_code(text))
    prose = HTML_COMMENT.sub(" ", PLACEHOLDER.sub(" ", body))
    prose = CITE_GROUP.sub(" ", prose)
    return {
        "引文键": sorted(CITE_KEY.findall(" ".join(CITE_GROUP.findall(body)))),
        "结果占位符": sorted(m.group(0) for m in PLACEHOLDER.finditer(body)),
        "主张标注": sorted(CLAIM_TAG_RE.findall(body)),
        "研究者问答标记": sorted(["问:" + q for q in Q_RE.findall(body)] + ["答:" + a for a in A_RE.findall(body)]),
        "正文数字": sorted(NUM_RE.findall(prose)),
        "标题": HEADING_RE.findall(body),
    }


def multiset_diff(before, after):
    b, c = Counter(before), Counter(after)
    return sorted((b - c).elements()), sorted((c - b).elements())


def cmd_polish_check(a):
    sb, sa = polish_signature(read_text(a.before)), polish_signature(read_text(a.after))
    errors, warns = [], []
    for k in ("引文键", "结果占位符", "主张标注", "研究者问答标记", "正文数字"):
        gone, new = multiset_diff(sb[k], sa[k])
        if gone or new:
            errors.append("%s 有变化：减少 %s；新增 %s" % (k, gone[:8] or "无", new[:8] or "无"))
    if sb["标题"] != sa["标题"]:
        warns.append("标题有变化（润色不应改章节标题）：%d → %d 个" % (len(sb["标题"]), len(sa["标题"])))
    print_findings(errors, warns)
    if not errors:
        print("通过：引文键、{{res}} 占位符、主张标注、问答标记与正文数字与润色前完全一致。")
    sys.exit(1 if errors else 0)


def stage_check(vault, name, files, project=None):
    """Error list for one named stage check (warnings are not stage blockers)."""
    md = [f for f in files if f.lower().endswith(".md") and os.path.isfile(f)]
    if name == "citations_resolved":
        return cite_problems(vault, md, strict=False)[0]
    if name == "citations_verified":
        return cite_problems(vault, md, strict=True)[0]
    if name == "results_linked":
        return results_problems(vault, md)[0]
    if name == "claims_aligned":
        return claim_problems(vault, md, strict=True, project=project)[0]
    if name == "no_open_questions":
        return ["%s：有未回答的 ⟦问：%s⟧" % (relpath(f, vault), q[:30])
                for f in md for q in open_questions(read_text(f))]
    return ["未知检查项：%s" % name]


# ------------------------------------------------------------------ report
def cmd_report(a):
    vault = vault_of(a)
    _, cm = cmap(vault)
    _, rm = rmap(vault)
    st_counts = dict(Counter(e.get("status") for e in cm["entries"].values()))
    pd = None
    try:
        pd = paper_dir(a, vault)
    except SystemExit:
        pass
    manuscript = None
    if pd and os.path.isdir(pd):
        # measure only the latest live manuscript so multi-stage copies do not double-count
        for fname in ("final.md", "polished.md", "draft.md", "outline.md"):
            cand = os.path.join(pd, fname)
            if os.path.isfile(cand):
                manuscript = cand
                break
    drafts = [manuscript] if manuscript else []
    cited = set()
    linked, bare, openq = 0, 0, 0
    seen_claims = set()
    for f in drafts:
        t = read_text(f)
        cited |= set(draft_keys(t))
        linked += len(PLACEHOLDER.findall(strip_code(t)))
        bare += len(bare_stats(t))
        openq += len(open_questions(t))
        if os.path.basename(f).lower() != "outline.md":
            seen_claims.update(CLAIM_TAG_RE.findall(strip_code(t)))
    outline_path = os.path.join(pd, "outline.md") if pd else None
    defined_claims = set(OUTLINE_CLAIM_ROW_RE.findall(read_text(outline_path))) if (outline_path and os.path.isfile(outline_path)) else set()
    defined_ids = {x[0] for x in defined_claims}
    unknown = len([k for k in cited if k not in cm["entries"]])
    ok = len([k for k in cited if cm["entries"].get(k, {}).get("status") in OK_STATUS])
    rv = load(os.path.join(pd, "reviews.json"), None) if pd else None
    rep = {"manuscript": relpath(manuscript, vault) if manuscript else None,
           "citations_total": len(cm["entries"]), "citation_status": st_counts, "cited_keys": len(cited),
           "cited_verified": ok, "cited_unknown": unknown,
           "cited_verified_rate": round(ok / len(cited), 3) if cited else None,
           "results_registered": len(rm["entries"]), "numbers_linked": linked, "bare_statistics": bare,
           "numbers_linked_rate": round(linked / (linked + bare), 3) if (linked + bare) else None,
           "claims_defined": len(defined_ids), "claims_covered": len(defined_ids & seen_claims),
           "open_questions": openq,
           "refine": {"current": rv["current"], "rounds": [{k: r[k] for k in ("version", "decision", "fatal", "major", "minor")}
                                                           for r in rv["rounds"]]} if rv else None}
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    print("引文表 %d 条 %s；正文引用 %d 个，其中已核验 %d、不在表中 %d（核验率 %s）" % (
        rep["citations_total"], st_counts, rep["cited_keys"], ok, unknown, rep["cited_verified_rate"]))
    print("结果登记 %d 个；正文已链接 %d 处、未链接统计量 %d 处（链接率 %s）" % (
        rep["results_registered"], linked, bare, rep["numbers_linked_rate"]))
    if defined_ids:
        print("主张覆盖：%d/%d（已定义 %d 条，正文已锚定 %d 条）" % (
            rep["claims_covered"], rep["claims_defined"], rep["claims_defined"], rep["claims_covered"]))
    print("未回答的 ⟦问⟧：%d" % openq)
    if rv:
        print("精修：当前 %s；" % rv["current"] + "；".join("%s %s" % (r["version"], r["decision"]) for r in rv["rounds"]))


# ------------------------------------------------------------------ review verify (advisory audit of reviewer output)
QUOTE_PATTERNS = [
    re.compile(r"「([^「」\n]{6,220})」"),
    re.compile(r"“([^“”\n]{6,220})”"),
    re.compile(r'"([^"\n]{12,220})"'),
]
SUGGESTED_BLOCK_RE = re.compile(r"```(?:yaml\s+)?suggested-references\s*\r?\n(.*?)```", re.S | re.I)


def _norm_ws(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def _extract_quotes(review_text):
    clean = strip_code(review_text)
    seen, out = set(), []
    for pat in QUOTE_PATTERNS:
        for m in pat.finditer(clean):
            q = m.group(1).strip()
            nq = _norm_ws(q)
            if nq and nq not in seen:
                seen.add(nq)
                out.append(q)
    return out


def _parse_suggested_refs(review_text):
    """Parse minimal YAML-like list items inside ```yaml suggested-references ...``` blocks."""
    refs = []
    for m in SUGGESTED_BLOCK_RE.finditer(review_text):
        cur = None
        for raw in m.group(1).splitlines():
            ln = raw.strip()
            if not ln or ln.startswith("#") or ln == "[]":
                continue
            if ln.startswith("- "):
                if cur and (cur.get("title") or cur.get("doi")):
                    refs.append(cur)
                cur = {}
                ln = ln[2:].strip()
            if cur is None:
                continue
            kv = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", ln)
            if kv:
                k, v = kv.group(1).lower(), kv.group(2).strip().strip("\"'")
                if v:
                    cur[k] = v
        if cur and (cur.get("title") or cur.get("doi")):
            refs.append(cur)
    return refs


def cmd_review_verify(a):
    """Advisory audit of a reviewer report: verify quoted manuscript passages (NFC) & suggested references."""
    if not os.path.isfile(a.review):
        sys.exit("找不到审稿报告：%s" % a.review)
    if not os.path.isfile(a.manuscript):
        sys.exit("找不到稿件文件：%s" % a.manuscript)
    rtext = read_text(a.review)
    mtext_norm = _norm_ws(read_text(a.manuscript))
    quotes = _extract_quotes(rtext)
    verified_q, unverified_q = [], []
    for q in quotes:
        if _norm_ws(q) in mtext_norm:
            verified_q.append(q)
        else:
            unverified_q.append(q)
    refs_raw = _parse_suggested_refs(rtext)
    refs_checked = []
    off = offline(a)
    for item in refs_raw:
        title = item.get("title", "")
        ctype = item.get("type", "chinese" if has_cjk(title) else "article")
        e = {"title": title, "year": item.get("year"), "doi": item.get("doi"), "type": ctype, "status": "unverified"}
        st = verify_entry(e, off)
        refs_checked.append({"title": title, "year": e.get("year"), "doi": e.get("doi"),
                             "status": st, "note": e.get("note_verify", "")})
    bad_refs = [r for r in refs_checked if r["status"] in ("mismatch", "unverified")]
    res = {"quotes_total": len(quotes), "quotes_verified": len(verified_q), "unverified_quotes": unverified_q,
           "suggested_refs": refs_checked}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for q in unverified_q:
            print("警告  UNVERIFIED_QUOTE（稿件中未找到该引述）：%s" % q[:80])
        for r in refs_checked:
            tag = "通过" if r["status"] == "verified" else ("人工" if r["status"] == "manual" else "警告")
            print("%s  推荐文献 [%s] %s%s" % (tag, r["status"], r["title"][:60], ("（%s）" % r["note"]) if r["note"] else ""))
        print("审稿复核：引述 %d/%d 匹配，未匹配 %d；推荐文献 %d 条（待核/不符 %d）。" % (
            len(verified_q), len(quotes), len(unverified_q), len(refs_checked), len(bad_refs)))
    sys.exit(1 if (a.strict and (unverified_q or bad_refs)) else 0)


# ------------------------------------------------------------------ cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--project")
    top = ap.add_subparsers(dest="group", required=True)

    c = top.add_parser("cite").add_subparsers(dest="cmd", required=True)
    p = c.add_parser("add")
    p.add_argument("--key", required=True); p.add_argument("--title", required=True); p.add_argument("--authors")
    p.add_argument("--year"); p.add_argument("--doi"); p.add_argument("--venue", default="")
    p.add_argument("--type", default="article", choices=["article", "book", "chinese", "legal"])
    p.add_argument("--doc-no"); p.add_argument("--effective"); p.add_argument("--locator")
    p.add_argument("--claim-scope"); p.add_argument("--replace", action="store_true")
    p.add_argument("--offline", action="store_true"); p.set_defaults(f=cmd_cite_add)
    p = c.add_parser("verify"); p.add_argument("--key"); p.add_argument("--all", action="store_true")
    p.add_argument("--offline", action="store_true"); p.set_defaults(f=cmd_cite_verify)
    p = c.add_parser("confirm"); p.add_argument("--key", required=True); p.add_argument("--note", default="")
    p.set_defaults(f=cmd_cite_confirm)
    p = c.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--strict", action="store_true")
    p.set_defaults(f=cmd_cite_check)
    p = c.add_parser("bib"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_cite_bib)
    p = c.add_parser("list"); p.set_defaults(f=cmd_cite_list)
    p = c.add_parser("from-note"); p.add_argument("files", nargs="+")
    p.add_argument("--replace", action="store_true"); p.add_argument("--offline", action="store_true")
    p.set_defaults(f=cmd_cite_from_note)
    p = c.add_parser("ris"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_cite_ris)
    p = c.add_parser("csl"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_cite_csl)

    def _imp(p):
        p.add_argument("--no-notes", action="store_true", help="do not create 03-Literature notes")
        p.add_argument("--verify", action="store_true", help="check each new entry against Crossref (network)")
        p.add_argument("--replace", action="store_true", help="overwrite duplicates (status resets to unverified)")
        p.add_argument("--dry-run", action="store_true"); p.add_argument("--offline", action="store_true")
    p = c.add_parser("import"); p.add_argument("files", nargs="+")
    p.add_argument("--format", default="auto", choices=["auto", "ris", "bibtex", "csl"])
    p.add_argument("--attach", action="store_true", help="copy referenced PDFs into 03-Literature/_sources")
    p.add_argument("--pdf-dir", help="folder to search PDFs by file name (EndNote .Data/PDF, Zotero storage)")
    _imp(p); p.set_defaults(f=cmd_cite_import)
    p = c.add_parser("zotero"); g = p.add_mutually_exclusive_group()
    g.add_argument("--user"); g.add_argument("--group"); g.add_argument("--base-url")
    p.add_argument("--collection"); p.add_argument("--limit", type=int)
    p.add_argument("--query", help="search the library (Zotero q=)"); p.add_argument("--list", action="store_true", help="with --query: only list matches")
    p.add_argument("--item", help="pull one item by Zotero item key"); p.add_argument("--notes", action="store_true", help="append Zotero child notes to literature notes")
    _imp(p); p.set_defaults(f=cmd_cite_zotero, attach=False, pdf_dir=None)
    p = c.add_parser("open"); p.add_argument("key"); p.add_argument("--print", action="store_true"); p.set_defaults(f=cmd_cite_open)
    p = c.add_parser("zotero-note"); p.add_argument("key"); p.add_argument("--zotero-key"); g = p.add_mutually_exclusive_group()
    g.add_argument("--user"); g.add_argument("--group"); g.add_argument("--base-url")
    p.add_argument("--yes", action="store_true", help="really write (default: preview only)"); p.add_argument("--offline", action="store_true")
    p.set_defaults(f=cmd_cite_zotero_note)

    r = top.add_parser("results").add_subparsers(dest="cmd", required=True)
    p = r.add_parser("register")
    p.add_argument("--id", required=True); p.add_argument("--value", required=True); p.add_argument("--label", default="")
    p.add_argument("--se"); p.add_argument("--n"); p.add_argument("--source"); p.add_argument("--script")
    p.add_argument("--no-source-reason"); p.add_argument("--note"); p.add_argument("--replace", action="store_true")
    p.set_defaults(f=cmd_results_register)
    p = r.add_parser("import"); p.add_argument("csv"); p.add_argument("--prefix", required=True)
    p.add_argument("--source"); p.add_argument("--script"); p.set_defaults(f=cmd_results_import)
    p = r.add_parser("render"); p.add_argument("draft"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_results_render)
    p = r.add_parser("check"); p.add_argument("files", nargs="+"); p.set_defaults(f=cmd_results_check)

    f = top.add_parser("refine").add_subparsers(dest="cmd", required=True)
    p = f.add_parser("start"); p.add_argument("draft"); p.set_defaults(f=cmd_refine_start)
    p = f.add_parser("record"); p.add_argument("--version", required=True)
    p.add_argument("--fatal", type=int); p.add_argument("--major", type=int)
    p.add_argument("--carried-fatal", type=int); p.add_argument("--carried-major", type=int)
    p.add_argument("--new-fatal", type=int); p.add_argument("--new-major", type=int)
    p.add_argument("--minor", type=int, default=0); p.add_argument("--scores", default=""); p.add_argument("--note")
    p.set_defaults(f=cmd_refine_record)
    p = f.add_parser("status"); p.set_defaults(f=cmd_refine_status)

    cl = top.add_parser("claim").add_subparsers(dest="cmd", required=True)
    p = cl.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--strict", action="store_true")
    p.set_defaults(f=cmd_claim_check)

    po = top.add_parser("polish").add_subparsers(dest="cmd", required=True)
    p = po.add_parser("scan"); p.add_argument("files", nargs="+"); p.add_argument("--strict", action="store_true")
    p.set_defaults(f=cmd_polish_scan)
    p = po.add_parser("check"); p.add_argument("--before", required=True); p.add_argument("--after", required=True)
    p.set_defaults(f=cmd_polish_check)

    rv_sub = top.add_parser("review").add_subparsers(dest="cmd", required=True)
    p = rv_sub.add_parser("verify")
    p.add_argument("--review", required=True); p.add_argument("--manuscript", required=True)
    p.add_argument("--offline", action="store_true"); p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_review_verify)

    p = top.add_parser("questions"); p.add_argument("files", nargs="+"); p.set_defaults(f=cmd_questions)
    p = top.add_parser("report"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_report)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    main()
