#!/usr/bin/env python3
"""Reference-manager exchange for Meta/citation-map.json (EndNote, Zotero and anything that speaks RIS/BibTeX/CSL-JSON).

Standard library only. Pure helpers: paper_tools.py wires them to
  cite import FILE...     RIS / BibTeX / CSL-JSON (EndNote and Zotero exports)
  cite ris | cite csl     export the table
  cite zotero             pull from the Zotero local API or the Zotero web API (read-only GET)

The citation table stays the single source of truth: imported entries start as 'unverified'
('manual' for Chinese-language items) and are never auto-confirmed.
"""
import hashlib
import json
import os
import re
import shutil
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_:\-]*$")
ZOTERO_ITEM_KEY = re.compile(r"^[A-Z0-9]{8}$")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
STOP = {"the", "a", "an", "of", "on", "in", "and", "for", "to", "with", "from", "by", "at", "is", "are",
        "does", "do", "how", "what", "why", "when", "new", "evidence", "study", "essay", "essays"}


class RefError(Exception):
    pass


# ------------------------------------------------------------------ small helpers
def is_cjk(s):
    return any("一" <= ch <= "鿿" for ch in (s or ""))


def decode_bytes(raw):
    """Reference managers on Chinese Windows often export GBK; try the sane encodings in order."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


_ACCENT = {'"': "\u0308", "'": "\u0301", chr(96): "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304",
           ".": "\u0307", "v": "\u030c", "u": "\u0306", "H": "\u030b", "c": "\u0327"}
_TEX_ACCENT = re.compile(r"\\([" + re.escape("\"'" + chr(96) + "^~=.") + r"]|[vuHc](?=[\s{]))\s*\{?([A-Za-z])\}?")


def clean(s):
    """Strip BibTeX/LaTeX decoration and collapse whitespace."""
    s = s or ""
    s = _TEX_ACCENT.sub(lambda m: unicodedata.normalize("NFC", m.group(2) + _ACCENT[m.group(1)]), s)
    for a, b in (("\\&", "&"), ("\\_", "_"), ("\\%", "%"), ("\\$", "$"), ("\\#", "#")):
        s = s.replace(a, b)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def norm_doi(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d)
    return d.strip()


def norm_title(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (t or "").lower())).strip()


def norm_author(name):
    """'Chetty, Raj' -> 'Raj Chetty' (the form Crossref returns); CJK names stay as written."""
    name = clean(name)
    if not name or is_cjk(name):
        return name
    if "," in name:
        last, first = name.split(",", 1)
        name = (first.strip() + " " + last.strip()).strip()
    return name.replace(",", " ")


def year4(s):
    m = re.search(r"(1[5-9]\d\d|20\d\d)", str(s or ""))
    return m.group(1) if m else None


def _first(d, *tags):
    for t in tags:
        v = d.get(t)
        if v:
            return v[0] if isinstance(v, list) else v
    return ""


def _blank():
    return {"title": "", "authors": [], "year": None, "doi": None, "venue": "", "raw_type": "", "id": "",
            "abstract": "", "keywords": [], "url": "", "volume": "", "issue": "", "pages": "", "files": []}


# ------------------------------------------------------------------ RIS (EndNote, Zotero, Reference Manager)
_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$")


def parse_ris(text):
    recs, cur, last = [], None, None
    for ln in text.lstrip("﻿").splitlines():
        m = _RIS_LINE.match(ln.rstrip())
        if not m:
            if cur is not None and last and ln.strip() and cur.get(last):
                cur[last][-1] += " " + ln.strip()
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            if cur:
                recs.append(_ris_rec(cur))
            cur, last = {"TY": [val]}, None
        elif cur is None:
            continue
        elif tag == "ER":
            recs.append(_ris_rec(cur))
            cur, last = None, None
        else:
            cur.setdefault(tag, []).append(val)
            last = tag
    if cur:
        recs.append(_ris_rec(cur))
    return recs


def _ris_rec(d):
    r = _blank()
    r["raw_type"] = _first(d, "TY").upper()
    r["title"] = clean(_first(d, "TI", "T1"))
    r["authors"] = [a for a in (norm_author(x) for x in (d.get("AU") or d.get("A1") or [])) if a]
    r["year"] = year4(_first(d, "PY", "Y1", "DA"))
    doi = _first(d, "DO", "DI")
    url = _first(d, "UR")
    if not doi and "doi.org/" in url:
        doi = url
    r["doi"] = norm_doi(doi) or None
    r["venue"] = clean(_first(d, "JO", "JF", "T2", "JA", "J2", "BT"))
    r["abstract"] = clean(_first(d, "AB", "N2"))
    r["keywords"] = [clean(k) for k in d.get("KW", []) if clean(k)]
    r["url"] = url
    r["volume"], r["issue"] = _first(d, "VL"), _first(d, "IS")
    sp, ep = _first(d, "SP"), _first(d, "EP")
    r["pages"] = (sp + "-" + ep) if sp and ep else sp
    r["files"] = list(d.get("L1", [])) + list(d.get("L2", []))
    for cand in (_first(d, "ID"), _first(d, "LB")):
        if cand and KEY_RE.match(cand):
            r["id"] = cand
            break
    return r


def to_ris(e):
    typ = {"book": "BOOK", "legal": "GEN"}.get(e.get("type"), "JOUR")
    out = ["TY  - " + typ, "ID  - " + e["key"], "TI  - " + (e.get("title") or "")]
    out += ["AU  - " + a for a in e.get("authors", [])]
    if e.get("year"):
        out.append("PY  - %s" % e["year"])
    if e.get("venue"):
        out.append(("T2  - " if typ == "BOOK" else "JO  - ") + e["venue"])
    for tag, fld in (("VL", "volume"), ("IS", "issue")):
        if e.get(fld):
            out.append("%s  - %s" % (tag, e[fld]))
    if e.get("pages"):
        pg = re.split(r"\s*-+\s*", str(e["pages"]).strip(), maxsplit=1)
        if pg[0]:
            out.append("SP  - " + pg[0])
        if len(pg) == 2 and pg[1]:
            out.append("EP  - " + pg[1])
    for tag, fld in (("DO", "doi"), ("UR", "url"), ("AB", "abstract")):
        if e.get(fld):
            out.append("%s  - %s" % (tag, e[fld]))
    out += ["KW  - " + k for k in e.get("keywords", [])]
    if e.get("type") == "legal":
        out.append("N1  - %s，%s 生效" % (e.get("doc_no"), e.get("effective")))
    out.append("N1  - ERC 核验状态：%s" % e.get("status"))
    out.append("ER  - ")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ BibTeX (Zotero, EndNote, JabRef)
def _scan_delim(text, pos, open_c="{", close_c="}"):
    depth, i, n = 0, pos, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return text[pos + 1:i], i + 1
        i += 1
    raise RefError("BibTeX 括号不匹配（文件可能被截断）")


def _scan_braced(text, pos):
    return _scan_delim(text, pos, "{", "}")


def _scan_quoted(text, pos):
    depth, i, n = 0, pos + 1, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == '"' and depth == 0:
            return text[pos + 1:i], i + 1
        i += 1
    raise RefError("BibTeX 引号不匹配（文件可能被截断）")


_FIELD = re.compile(r"[\s,]*([A-Za-z][\w\-:]*)\s*=\s*")
_HEAD = re.compile(r"@(\w+)\s*([{(])")
_BARE_VAL = re.compile(r"[^,\s#}]+")


def parse_bibtex(text):
    text = text.lstrip("﻿")
    recs, i, n = [], 0, len(text)
    while True:
        i = text.find("@", i)
        if i < 0:
            break
        m = _HEAD.match(text, i)
        if not m:
            i += 1
            continue
        etype, opener = m.group(1).lower(), m.group(2)
        if etype in ("comment", "preamble", "string"):
            _, i = _scan_delim(text, m.end() - 1, opener, "}" if opener == "{" else ")")
            continue
        comma = text.find(",", m.end())
        if comma < 0:
            break
        key, pos, fields = text[m.end():comma].strip(), comma + 1, {}
        close = "}" if opener == "{" else ")"
        while pos < n:
            while pos < n and text[pos] in " \t\r\n,":
                pos += 1
            if pos >= n or text[pos] == close:
                pos += 1
                break
            fm = _FIELD.match(text, pos)
            if not fm:
                pos += 1
                continue
            name, pos, val = fm.group(1).lower(), fm.end(), ""
            while pos < n:
                if text[pos] == "{":
                    part, pos = _scan_braced(text, pos)
                elif text[pos] == '"':
                    part, pos = _scan_quoted(text, pos)
                else:
                    em = _BARE_VAL.match(text, pos)
                    part, pos = (em.group(0), em.end()) if em else ("", pos + 1)
                val += part
                while pos < n and text[pos] in " \t\r\n":
                    pos += 1
                if pos < n and text[pos] == "#":
                    pos += 1
                    while pos < n and text[pos] in " \t\r\n":
                        pos += 1
                    continue
                break
            fields[name] = val
        recs.append(_bib_rec(etype, key, fields))
        i = pos
    return recs


def _bib_rec(etype, key, f):
    r = _blank()
    r["raw_type"], r["id"] = etype, (key if KEY_RE.match(key) else "")
    r["title"] = clean(f.get("title", ""))
    r["authors"] = [a for a in (norm_author(x) for x in re.split(r"\s+and\s+", f.get("author", ""), flags=re.I)) if a]
    r["year"] = year4(f.get("year") or f.get("date"))
    r["doi"] = norm_doi(f.get("doi", "")) or None
    r["venue"] = clean(f.get("journal") or f.get("journaltitle") or f.get("booktitle") or f.get("publisher") or "")
    r["abstract"] = clean(f.get("abstract", ""))
    r["keywords"] = [k for k in (clean(x) for x in re.split(r"[,;]", f.get("keywords", f.get("keyword", "")))) if k]
    r["url"] = clean(f.get("url", ""))
    r["volume"], r["issue"] = clean(f.get("volume", "")), clean(f.get("number", f.get("issue", "")))
    r["pages"] = clean(f.get("pages", "")).replace("--", "-")
    r["files"] = parse_bib_files(f.get("file", ""))
    return r


def parse_bib_files(val):
    """Zotero: 'desc:path:mime;desc:path:mime' with ':' and '\\' escaped; JabRef: ':path:PDF'."""
    out = []
    for item in re.split(r"(?<!\\);", val or ""):
        item = item.strip()
        if not item:
            continue
        toks = [t.replace("\\:", ":").replace("\\\\", "\\") for t in re.split(r"(?<!\\):", item)]
        if len(toks) == 1:
            path = toks[0]
        elif len(toks) >= 3 and len(toks[1]) == 1 and toks[1].isalpha():
            path = toks[1] + ":" + toks[2]
        else:
            path = toks[1] if len(toks) >= 3 or not toks[0] else toks[0]
        if path:
            out.append(path)
    return out


# ------------------------------------------------------------------ CSL-JSON (Zotero, Pandoc, Word)
def parse_csl(text):
    data = json.loads(text.lstrip("﻿"))
    items = data.get("items", [data]) if isinstance(data, dict) else data
    recs = []
    for it in items:
        if not isinstance(it, dict):
            continue
        r = _blank()
        r["raw_type"] = str(it.get("type") or "").lower()
        r["id"] = str(it.get("id") or "") if KEY_RE.match(str(it.get("id") or "")) else ""
        r["title"] = clean(it.get("title", ""))
        for a in it.get("author", []) or []:
            if a.get("literal"):
                nm = a["literal"]
            elif is_cjk((a.get("family") or "") + (a.get("given") or "")):
                nm = (a.get("family") or "") + (a.get("given") or "")
            else:
                nm = " ".join(x for x in (a.get("given"), a.get("family")) if x)
            if clean(nm):
                r["authors"].append(clean(nm))
        iss = it.get("issued") or {}
        dp = (iss.get("date-parts") or [[None]])[0]
        r["year"] = year4(dp[0] if dp else None) or year4(iss.get("raw") or iss.get("literal"))
        r["doi"] = norm_doi(it.get("DOI", "")) or None
        r["venue"] = clean(it.get("container-title") or it.get("publisher") or "")
        r["abstract"] = clean(it.get("abstract", ""))
        kw = it.get("keyword") or ""
        r["keywords"] = [k for k in (clean(x) for x in re.split(r"[,;]", kw if isinstance(kw, str) else ",".join(kw))) if k]
        r["url"] = it.get("URL", "") or ""
        r["volume"], r["issue"] = str(it.get("volume") or ""), str(it.get("issue") or "")
        r["pages"] = str(it.get("page") or "").replace("--", "-")
        recs.append(r)
    return recs


def _csl_name(n):
    if is_cjk(n):
        return {"literal": n}
    parts = n.split()
    if len(parts) < 2:
        return {"literal": n}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def to_csl(e):
    typ = {"book": "book", "legal": "legislation"}.get(e.get("type"), "article-journal")
    o = {"id": e["key"], "type": typ, "title": e.get("title", ""), "author": [_csl_name(a) for a in e.get("authors", [])]}
    if e.get("year"):
        o["issued"] = {"date-parts": [[int(e["year"])]]} if str(e["year"]).isdigit() else {"literal": str(e["year"])}
    for k, fld in (("container-title", "venue"), ("DOI", "doi"), ("URL", "url"), ("abstract", "abstract"),
                   ("volume", "volume"), ("issue", "issue"), ("page", "pages")):
        if e.get(fld):
            o[k] = e[fld]
    if e.get("keywords"):
        o["keyword"] = ", ".join(e["keywords"])
    o["note"] = "ERC 核验状态：%s" % e.get("status")
    return o


# ------------------------------------------------------------------ format detection
def detect_format(path, text):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".ris",):
        return "ris"
    if ext in (".bib", ".bibtex"):
        return "bibtex"
    if ext == ".json":
        return "csl"
    head = text.lstrip("﻿").lstrip()
    if re.search(r"^TY\s{1,2}-", text, re.M):
        return "ris"
    if head.startswith("@"):
        return "bibtex"
    if head[:1] in "[{":
        return "csl"
    raise RefError("无法判断文件格式（支持 .ris / .bib / .json）：%s" % path)


def parse_text(fmt, text):
    return {"ris": parse_ris, "bibtex": parse_bibtex, "csl": parse_csl}[fmt](text)


# ------------------------------------------------------------------ classification, keys, duplicates
_RIS_BOOK, _RIS_LEGAL = {"BOOK", "EBOOK", "EDBOOK", "CHAP", "ECHAP"}, {"BILL", "STAT", "CASE", "LEGAL"}
_BIB_BOOK = {"book", "inbook", "incollection", "proceedings", "collection", "mvbook"}
_CSL_BOOK, _CSL_LEGAL = {"book", "chapter", "entry", "entry-encyclopedia"}, {"legislation", "bill", "legal_case", "regulation", "treaty"}


def decide_type(rec):
    """-> 'article' | 'book' | 'chinese' | None (legal items need a doc number and effective date: register by hand)."""
    t = rec.get("raw_type", "")
    if t.upper() in _RIS_LEGAL or t in _CSL_LEGAL:
        return None
    if is_cjk(rec.get("title")):
        return "chinese"
    if t.upper() in _RIS_BOOK or t in _BIB_BOOK or t in _CSL_BOOK:
        return "book"
    return "article"


def _slug(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def make_key(rec, taken):
    cand = rec.get("id") or ""
    if cand and KEY_RE.match(cand) and not ZOTERO_ITEM_KEY.match(cand):
        base = cand
    else:
        a = rec["authors"][0] if rec.get("authors") else ""
        fam = "zh" if is_cjk(a) or is_cjk(rec.get("title")) else (_slug(a.split()[-1]) if a else "")
        fam = fam if fam and fam[0].isalpha() else "anon"
        word = ""
        for w in re.findall(r"[A-Za-z]{4,}", rec.get("title") or ""):
            if w.lower() not in STOP:
                word = w.lower()
                break
        if not word:
            word = hashlib.sha1((rec.get("title") or "").encode("utf-8")).hexdigest()[:4]
        base = "%s%s%s" % (fam, rec.get("year") or "nd", word)
    key, n = base, 0
    while key in taken:
        key = base + (chr(97 + n) if n < 26 else str(n))
        n += 1
    return key


def build_dup_index(entries):
    """Build O(1) lookup index for duplicate detection across batch imports."""
    idx = {"doi": {}, "title": {}}
    for k, e in entries.items():
        index_entry(idx, k, e)
    return idx


def index_entry(idx, key, e):
    d = norm_doi(e.get("doi"))
    if d and d not in idx["doi"]:
        idx["doi"][d] = key
    nt = norm_title(e.get("title"))
    if nt:
        idx["title"].setdefault(nt, []).append((key, str(e.get("year") or "")))


def find_duplicate(rec, entries, index=None):
    d, nt = norm_doi(rec.get("doi")), norm_title(rec.get("title"))
    if index is not None:
        if d and d in index["doi"]:
            return index["doi"][d]
        if nt and nt in index["title"]:
            ry = str(rec.get("year") or "")
            for k, ey in index["title"][nt]:
                if not ry or not ey or ry == ey:
                    return k
        return None
    if d:
        for k, e in entries.items():
            if norm_doi(e.get("doi")) == d:
                return k
    if nt:
        for k, e in entries.items():
            if norm_title(e.get("title")) == nt and (not rec.get("year") or not e.get("year")
                                                      or str(rec["year"]) == str(e["year"])):
                return k
    return None


def to_entry(rec, key, typ, stamp, label):
    e = {"key": key, "title": rec["title"], "authors": rec["authors"], "year": rec.get("year"),
         "doi": rec.get("doi"), "venue": rec.get("venue", ""), "type": typ, "status": "unverified",
         "added": stamp, "imported_from": label}
    for fld in ("abstract", "keywords", "url", "volume", "issue", "pages"):
        if rec.get(fld):
            e[fld] = rec[fld]
    if ZOTERO_ITEM_KEY.match(rec.get("id") or ""):
        e["zotero_key"] = rec["id"]
    return e


# ------------------------------------------------------------------ attachments (PDF only, copied, never moved)
def _as_path(p):
    p = p.strip()
    if p.lower().startswith("file:"):
        p = urllib.parse.unquote(urllib.parse.urlparse(p).path)
        if re.match(r"^/[A-Za-z]:", p):
            p = p[1:]
    return p


def build_pdf_index(pdf_dir):
    """Walk pdf_dir once and index filenames to absolute paths for O(1) attachment lookup."""
    idx = {}
    if not pdf_dir or not os.path.isdir(pdf_dir):
        return idx
    for root, _, files in os.walk(pdf_dir):
        for fn in files:
            if fn.lower().endswith(".pdf") and fn not in idx:
                idx[fn] = os.path.abspath(os.path.join(root, fn))
    return idx


def resolve_pdf(paths, base_dir, pdf_dir, pdf_index=None):
    for raw in paths:
        p = _as_path(raw)
        if not p.lower().endswith(".pdf"):
            continue
        if not p.lower().startswith(("internal-pdf:", "http:", "https:")):
            cand = p if os.path.isabs(p) else os.path.join(base_dir or ".", p)
            if os.path.isfile(cand):
                return os.path.abspath(cand)
        if pdf_index is not None:
            hit = pdf_index.get(os.path.basename(p.replace("\\", "/")))
            if hit:
                return hit
        elif pdf_dir:
            name = os.path.basename(p.replace("\\", "/"))
            for root, _, files in os.walk(pdf_dir):
                if name in files:
                    return os.path.abspath(os.path.join(root, name))
    return None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def attach_pdf(vault, key, src):
    """Copy src to 03-Literature/_sources/<key>.pdf. Returns (relpath, sha, status) where status is
    'copied' | 'same' | 'conflict' (a different file already has that name: left untouched)."""
    dst_dir = os.path.join(vault, "03-Literature", "_sources")
    dst = os.path.join(dst_dir, re.sub(r"[^\w.\-]", "_", key) + ".pdf")
    rel = os.path.relpath(dst, vault).replace("\\", "/")
    sha = file_sha256(src)
    if os.path.exists(dst):
        return rel, sha, ("same" if file_sha256(dst) == sha else "conflict")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copyfile(src, dst)
    return rel, sha, "copied"


# ------------------------------------------------------------------ literature note stub
def _q(s):
    return '"%s"' % (s or "").replace("\\", "\\\\").replace('"', '\\"')


def note_rel(key):
    return "03-Literature/" + re.sub(r"[^\w.\-]", "_", key) + ".md"


def note_text(e, template, src_rel=None, sha=None, today=""):
    authors = ", ".join(a.replace(",", " ") for a in e.get("authors", []))
    fm = ["---", "type: literature", "cite_key: " + e["key"], "title: " + _q(e["title"]),
          "authors: [%s]" % authors, "year: %s" % (e.get("year") or ""), "journal: " + _q(e.get("venue")),
          "doi: " + _q(e.get("doi")), "url: " + _q(e.get("url")), 'research_field: ""', "method: []",
          'locator: ""', 'claim_scope: ""', "tags: [imported]", "status: unread",
          "sources: [%s]" % (src_rel or ""), "sha256: " + _q(sha), "updated: " + today, "verification: unverified"]
    if e.get("type") in ("chinese", "book"):
        fm.insert(3, "cite_type: " + e["type"])
    fm.append("---")
    body = ""
    t = (template or "").lstrip("\ufeff").replace("\r\n", "\n")
    if t.startswith("---\n") and "\n---\n" in t[3:]:
        body = t[3:].split("\n---\n", 1)[1]
    if not body.strip():
        body = "\n# 一、研究问题与定位\n\n# 二、识别策略与核心假设\n\n# 三、实证结果与经济量级\n\n# 四、对本人研究的启示\n"
    body = body.replace("`[[双链]]`", "双链")  # keep the stub free of placeholder wikilinks
    tail = ["", "## 导入信息", "- 来源：%s（%s）；元数据与摘要来自参考文献软件，**未经核实**，核对原文后再改 verification。" % (
        e.get("imported_from", ""), today)]
    if e.get("keywords"):
        tail.append("- 关键词：" + "；".join(e["keywords"]))
    if e.get("abstract"):
        tail += ["", "### 导入的摘要（未核实）", e["abstract"]]
    return "\n".join(fm) + "\n" + body.rstrip("\n") + "\n" + "\n".join(tail) + "\n"


# ------------------------------------------------------------------ Zotero API (read-only GET)
def _open(req, timeout):
    """urlopen that never routes loopback traffic through HTTP(S)_PROXY (a system proxy answers 503 for 127.0.0.1)."""
    host = (urllib.parse.urlparse(req.full_url).hostname or "").lower()
    if host in LOCAL_HOSTS or host == "::1":
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def check_base(base, offline_flag):
    u = urllib.parse.urlparse(base)
    host = (u.hostname or "").lower()
    local = host in LOCAL_HOSTS
    if u.scheme not in ("http", "https"):
        raise RefError("不支持的地址：%s" % base)
    if u.scheme == "http" and not local:
        raise RefError("非本机地址必须使用 https（避免明文发送 API 密钥）：%s" % base)
    if offline_flag and not local:
        raise RefError("--offline / ERC_OFFLINE=1 下只允许连接本机 Zotero。")


def zotero_fetch(base, api_key=None, collection=None, limit=None, timeout=20):
    hdrs = _hdrs(api_key)
    path = ("/collections/%s/items/top" % urllib.parse.quote(collection)) if collection else "/items/top"
    items, start, page = [], 0, 100
    while True:
        url = "%s%s?format=csljson&limit=%d&start=%d" % (base.rstrip("/"), path, page, start)
        data = _http(url, hdrs, timeout=timeout)
        batch = data.get("items", []) if isinstance(data, dict) else data
        if not batch:
            break
        items.extend(batch)
        if limit and len(items) >= limit:
            items = items[:limit]
            break
        if len(batch) < page:
            break
        start += page
    return items


# ------------------------------------------------------------------ Zotero extras (inspired by jbaiter/zotero-cli, MIT; reimplemented with the standard library)
def _http(url, hdrs, data=None, timeout=20):
    try:
        req = urllib.request.Request(url, headers=hdrs, data=data)
        with _open(req, timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as ex:
        hint = {403: "（Zotero 7：设置 → 高级 → 勾选“允许此计算机上的其他应用程序与 Zotero 通信”；网络库请检查 API 密钥权限）",
                404: "（用户/群组 ID、集合或条目 key 不存在）"}.get(ex.code, "")
        raise RefError("Zotero 返回 HTTP %d %s" % (ex.code, hint))
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise RefError("连接 Zotero 失败：%s（本机请先启动 Zotero 并开启本地 API）" % ex)


def _hdrs(api_key):
    h = {"Zotero-API-Version": "3", "User-Agent": "erc-paper-tools"}
    if api_key:
        h["Zotero-API-Key"] = api_key
    return h


def zotero_search(base, api_key, query, limit=None):
    """Full-text style search (Zotero q=); returns CSL-JSON items."""
    qs = urllib.parse.urlencode({"format": "csljson", "q": query, "limit": limit or 50}, quote_via=urllib.parse.quote)
    url = "%s/items/top?%s" % (base.rstrip("/"), qs)
    data = _http(url, _hdrs(api_key))
    return data.get("items", []) if isinstance(data, dict) else data


def zotero_one(base, api_key, item):
    data = _http("%s/items/%s?format=csljson" % (base.rstrip("/"), urllib.parse.quote(item)), _hdrs(api_key))
    items = data.get("items", [data]) if isinstance(data, dict) else data
    return [x for x in items if isinstance(x, dict) and x.get("title") is not None]


def zotero_notes(base, api_key, item):
    """Raw HTML of the child notes of one item."""
    url = "%s/items/%s/children?format=json&itemType=note&limit=100" % (base.rstrip("/"), urllib.parse.quote(item))
    data = _http(url, _hdrs(api_key))
    out = []
    for x in data if isinstance(data, list) else []:
        d = x.get("data", x)
        if d.get("note"):
            out.append(d["note"])
    return out


def html_to_text(h):
    import html as _h
    h = re.sub(r"<\s*(br|/p|/div|/h[1-6]|/li)\s*/?>", "\n", h, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", _h.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def zotero_post_note(base, api_key, parent, html_note, tags=("erc-exported",)):
    """Create one child note under 'parent' (web API write; never edits or deletes existing items)."""
    import uuid
    if not api_key:
        raise RefError("写入 Zotero 需要有写权限的 API 密钥（环境变量 ZOTERO_API_KEY）。")
    hdrs = _hdrs(api_key)
    hdrs["Content-Type"] = "application/json"
    hdrs["Zotero-Write-Token"] = uuid.uuid4().hex
    body = json.dumps([{"itemType": "note", "parentItem": parent, "note": html_note,
                        "tags": [{"tag": t} for t in tags]}]).encode("utf-8")
    res = _http("%s/items" % base.rstrip("/"), hdrs, data=body)
    if isinstance(res, dict) and res.get("failed"):
        raise RefError("Zotero 拒绝写入：%s" % json.dumps(res["failed"], ensure_ascii=False)[:300])
    return res
