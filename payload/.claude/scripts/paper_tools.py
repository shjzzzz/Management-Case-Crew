#!/usr/bin/env python3
"""Paper-writing support: citation table, results ledger, refinement decisions, checks, report.

Standard library only. Inspired by the idea (not the code) of PaperOrchestra: the writer may only
cite keys that exist in a verified citation table, and every number must trace to registered results.

  cite add --key K --title T [--authors "A; B"] [--year Y] [--doi D] [--venue V]
           [--type article|book|chinese|legal] [--doc-no NO --effective DATE] [--offline]
  cite verify [--key K | --all] [--offline]   re-check unverified/mismatch entries against Crossref
  cite confirm --key K --note TEXT            the researcher confirms a source by hand (asks for permission)
  cite check DRAFT.md...                      unknown keys (error), unverified keys (warning), unused entries
  cite bib [-o refs.bib]                      BibTeX of the table
  cite list
  results register --id ID --value V [--label L --se S --n N --source FILE --script FILE --note T]
  results import CSV --prefix P --source FILE [--script FILE]   register every cell as P.<row>.<col>
  results render DRAFT.md [-o OUT.md]         fill {{res:id}} / {{res:id:3}} placeholders from the ledger
  results check DRAFT.md...                   unknown ids, stale sources, bare statistics not linked to results
  refine start DRAFT.md                       snapshot paper/versions/v0.md
  refine record --version vN --fatal F --major M --minor m --scores a=5,b=6
                                              record a review and get the accept / revert decision
  refine status
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
import urllib.parse
import urllib.request

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
    if e.get("type") in ("chinese", "legal"):
        if e.get("status") not in OK_STATUS:
            e["status"] = "manual"
        return e["status"]
    if off:
        if e.get("status") not in OK_STATUS:
            e["status"] = "unverified"
        return e["status"]
    cands = crossref_fetch(doi=e["doi"]) if e.get("doi") else crossref_fetch(title=e["title"])
    if not cands:
        e["status"] = "unverified"
        e["note_verify"] = "Crossref 没有返回结果（或网络不可用）"
        return e["status"]

    def year_ok_for(c):
        return (not e.get("year")) or (not c.get("year")) or abs(int(e["year"]) - int(c["year"])) <= 1

    # the same title often has several records (working paper vs journal version): prefer one whose
    # title AND year both match; otherwise report the closest title
    viable = [c for c in cands if similar(c["title"], e["title"]) >= 0.9 and year_ok_for(c)]
    best = max(viable or cands, key=lambda c: similar(c["title"], e["title"]))
    ratio = similar(best["title"], e["title"])
    year_ok = year_ok_for(best)
    if ratio >= 0.9 and year_ok:
        e["status"], e["verified_by"] = "verified", "crossref"
        e["doi"] = e.get("doi") or best.get("doi")
        if not e.get("year") and best.get("year"):
            e["year"] = best["year"]
        if not e.get("venue") and best.get("venue"):
            e["venue"] = best["venue"]
        if not e.get("authors") and best.get("authors"):
            e["authors"] = best["authors"]
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


def cite_problems(vault, files, strict):
    """(errors, warnings, used_keys) for the given draft files."""
    _, m = cmap(vault)
    errors, warns, used = [], [], set()
    for f in files:
        for k in draft_keys(read_text(f)):
            used.add(k)
            e = m["entries"].get(k)
            rel = os.path.relpath(f, vault).replace("\\", "/")
            if e is None:
                errors.append("%s：引用键 @%s 不在引文表中" % (rel, k))
            elif e.get("status") not in OK_STATUS:
                (errors if strict else warns).append("%s：@%s 状态为 %s（未核验）" % (rel, k, e.get("status")))
    return sorted(set(errors)), sorted(set(warns)), used


def cmd_cite_check(a):
    vault = vault_of(a)
    errors, warns, used = cite_problems(vault, a.files, a.strict)
    _, m = cmap(vault)
    for x in errors:
        print("错误  " + x)
    for x in warns:
        print("警告  " + x)
    unused = sorted(set(m["entries"]) - used)
    if unused:
        print("提示  引文表中未被引用：" + ", ".join(unused))
    print("引用键 %d 个；错误 %d，警告 %d。" % (len(used), len(errors), len(warns)))
    sys.exit(1 if errors else 0)


def bibtex(e):
    typ = {"book": "book", "legal": "misc"}.get(e.get("type"), "article")
    f = [("title", e["title"]), ("author", " and ".join(e.get("authors", []))), ("year", e.get("year")),
         ("journal" if typ == "article" else "publisher", e.get("venue")), ("doi", e.get("doi"))]
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


# ------------------------------------------------------------------ results
def rmap(vault):
    path = os.path.join(vault, RES_REL)
    return path, load(path, {"version": 1, "entries": {}})


def to_float(s):
    try:
        return float(str(s).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def register(vault, m, rid, value, label="", se=None, n=None, source=None, script=None, note=""):
    if not re.match(r"^[A-Za-z0-9_.\-:]+$", rid):
        sys.exit("id 只能含字母数字、下划线、点、冒号、连字符：%s" % rid)
    e = {"id": rid, "value": str(value), "numeric": to_float(value), "label": label, "se": se, "n": n,
         "note": note, "registered": now()}
    for fld, p in (("source", source), ("script", script)):
        if p:
            ap = os.path.abspath(p if os.path.isabs(p) else os.path.join(vault, p))
            if not orc.inside(ap, vault) or not os.path.isfile(ap):
                sys.exit("%s 必须是库内已存在的文件：%s" % (fld, p))
            e[fld] = os.path.relpath(ap, vault).replace("\\", "/")
            if fld == "source":
                e["source_sha256"] = sha256(ap)
    m["entries"][rid] = e


def cmd_results_register(a):
    vault = vault_of(a)
    path, m = rmap(vault)
    if a.id in m["entries"] and not a.replace:
        sys.exit("id 已存在：%s（要覆盖请加 --replace）" % a.id)
    register(vault, m, a.id, a.value, a.label, a.se, a.n, a.source, a.script, a.note or "")
    save(path, m)
    orc.ledger_append(vault, "result_register", id=a.id)
    e = m["entries"][a.id]
    print("%s = %s%s" % (a.id, e["value"], "" if e.get("source") else "  （警告：没有 --source，无法追溯来源）"))


def cmd_results_import(a):
    vault = vault_of(a)
    path, m = rmap(vault)
    csv_path = os.path.abspath(a.csv if os.path.isabs(a.csv) else os.path.join(vault, a.csv))
    if not os.path.isfile(csv_path):
        sys.exit("找不到 %s" % a.csv)
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        sys.exit("CSV 至少需要表头和一行数据。")
    header, count = rows[0], 0
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        rowkey = re.sub(r"[^\w\-]+", "_", r[0].strip())
        for j in range(1, min(len(header), len(r))):
            if r[j].strip() == "":
                continue
            rid = "%s.%s.%s" % (a.prefix, rowkey, re.sub(r"[^\w\-]+", "_", header[j].strip()))
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
    target = a.output or re.sub(r"\.md$", ".rendered.md", a.draft)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("已写入 %s" % target)


def bare_stats(text):
    t = strip_code(text)
    t = PLACEHOLDER.sub(" ", t)
    t = CITE_GROUP.sub(" ", t)
    t = re.sub(r"https?://\S+|\b(?:19|20)\d{2}\b", " ", t)
    hits = []
    for i, line in enumerate(t.split("\n"), 1):
        for mo in STAT_RE.finditer(line):
            if mo.group(1).replace(" ", "") not in SAFE_DECIMALS:
                hits.append((i, mo.group(1)))
    return hits


def results_problems(vault, files):
    _, m = rmap(vault)
    errors, warns = [], []
    for f in files:
        text, rel = read_text(f), os.path.relpath(f, vault).replace("\\", "/")
        for mo in PLACEHOLDER.finditer(strip_code(text)):
            e = m["entries"].get(mo.group(1))
            if e is None:
                errors.append("%s：{{res:%s}} 不在结果登记簿中" % (rel, mo.group(1)))
            elif e.get("source"):
                sp = os.path.join(vault, e["source"])
                if not os.path.isfile(sp) or sha256(sp) != e.get("source_sha256"):
                    warns.append("%s：%s 的来源文件 %s 已变化或缺失，登记值可能过期" % (rel, mo.group(1), e["source"]))
        bs = bare_stats(text)
        if bs:
            warns.append("%s：有 %d 处统计量没有链接到结果登记簿（例如第 %d 行的 %s）" % (rel, len(bs), bs[0][0], bs[0][1]))
    return sorted(set(errors)), sorted(set(warns))


def cmd_results_check(a):
    vault = vault_of(a)
    errors, warns = results_problems(vault, a.files)
    for x in errors:
        print("错误  " + x)
    for x in warns:
        print("警告  " + x)
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
            print("%s：⟦问：%s⟧" % (os.path.relpath(f, vault).replace("\\", "/"), q))
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
    orc.ledger_append(vault, "refine_start", draft=os.path.relpath(src, vault).replace("\\", "/"))
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
def stage_check(vault, name, files):
    md = [f for f in files if f.lower().endswith(".md") and os.path.isfile(f)]
    if name == "citations_resolved":
        e, _, _ = cite_problems(vault, md, strict=False)
        return e
    if name == "citations_verified":
        e, _, _ = cite_problems(vault, md, strict=True)
        return e
    if name == "results_linked":
        e, _ = results_problems(vault, md)
        return e
    if name == "no_open_questions":
        return ["%s：有未回答的 ⟦问：%s⟧" % (os.path.relpath(f, vault).replace("\\", "/"), q[:30])
                for f in md for q in open_questions(read_text(f))]
    return ["未知检查项：%s" % name]


# ------------------------------------------------------------------ report
def cmd_report(a):
    vault = vault_of(a)
    _, cm = cmap(vault)
    _, rm = rmap(vault)
    st_counts = {}
    for e in cm["entries"].values():
        st_counts[e.get("status")] = st_counts.get(e.get("status"), 0) + 1
    pd = None
    try:
        pd = paper_dir(a, vault)
    except SystemExit:
        pass
    drafts = []
    if pd and os.path.isdir(pd):
        # only the live manuscript files: versions/ and worklogs quote keys and ids in prose
        drafts = [os.path.join(pd, f) for f in ("outline.md", "draft.md", "final.md") if os.path.isfile(os.path.join(pd, f))]
    cited = set()
    unknown, linked, bare, openq = 0, 0, 0, 0
    for f in drafts:
        t = read_text(f)
        cited |= set(draft_keys(t))
        linked += len(PLACEHOLDER.findall(strip_code(t)))
        bare += len(bare_stats(t))
        openq += len(open_questions(t))
    unknown = len([k for k in cited if k not in cm["entries"]])
    ok = len([k for k in cited if cm["entries"].get(k, {}).get("status") in OK_STATUS])
    rv = load(os.path.join(pd, "reviews.json"), None) if pd else None
    rep = {"citations_total": len(cm["entries"]), "citation_status": st_counts, "cited_keys": len(cited),
           "cited_verified": ok, "cited_unknown": unknown,
           "cited_verified_rate": round(ok / len(cited), 3) if cited else None,
           "results_registered": len(rm["entries"]), "numbers_linked": linked, "bare_statistics": bare,
           "numbers_linked_rate": round(linked / (linked + bare), 3) if (linked + bare) else None,
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
    print("未回答的 ⟦问⟧：%d" % openq)
    if rv:
        print("精修：当前 %s；" % rv["current"] + "；".join("%s %s" % (r["version"], r["decision"]) for r in rv["rounds"]))


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
    p.add_argument("--doc-no"); p.add_argument("--effective"); p.add_argument("--replace", action="store_true")
    p.add_argument("--offline", action="store_true"); p.set_defaults(f=cmd_cite_add)
    p = c.add_parser("verify"); p.add_argument("--key"); p.add_argument("--all", action="store_true")
    p.add_argument("--offline", action="store_true"); p.set_defaults(f=cmd_cite_verify)
    p = c.add_parser("confirm"); p.add_argument("--key", required=True); p.add_argument("--note", default="")
    p.set_defaults(f=cmd_cite_confirm)
    p = c.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--strict", action="store_true")
    p.set_defaults(f=cmd_cite_check)
    p = c.add_parser("bib"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_cite_bib)
    p = c.add_parser("list"); p.set_defaults(f=cmd_cite_list)

    r = top.add_parser("results").add_subparsers(dest="cmd", required=True)
    p = r.add_parser("register")
    p.add_argument("--id", required=True); p.add_argument("--value", required=True); p.add_argument("--label", default="")
    p.add_argument("--se"); p.add_argument("--n"); p.add_argument("--source"); p.add_argument("--script")
    p.add_argument("--note"); p.add_argument("--replace", action="store_true"); p.set_defaults(f=cmd_results_register)
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

    p = top.add_parser("questions"); p.add_argument("files", nargs="+"); p.set_defaults(f=cmd_questions)
    p = top.add_parser("report"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_report)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    main()
