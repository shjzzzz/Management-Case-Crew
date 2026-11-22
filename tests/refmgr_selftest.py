#!/usr/bin/env python3
"""Self-test for EndNote / Zotero exchange (cite import | ris | csl | zotero). Usage:
  python tests/refmgr_selftest.py <vault>/.claude/scripts/paper_tools.py <installed vault>
Runs offline (ERC_OFFLINE=1); the Zotero test talks to a throw-away server on 127.0.0.1."""
import http.server, json, os, re, subprocess, sys, tempfile, threading

PT, VAULT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, os.path.dirname(PT))
import refmgr  # noqa: E402

fails = 0
LAST = ""


def check(cond, name):
    global fails
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        print("    last output: " + LAST[-600:].replace("\n", "\n    "))
    fails += 0 if cond else 1


def pt(vault, *args, env=None):
    global LAST
    e = dict(os.environ, ERC_OFFLINE="1", PYTHONIOENCODING="utf-8")
    e.update(env or {})
    r = subprocess.run([sys.executable, "-X", "utf8", PT, "--vault", vault] + list(args),
                       capture_output=True, text=True, encoding="utf-8", env=e)
    LAST = r.stdout + r.stderr
    return r.returncode, LAST


def cmap(vault):
    with open(os.path.join(vault, "Meta", "citation-map.json"), encoding="utf-8") as fh:
        return json.load(fh)["entries"]


tmp = tempfile.mkdtemp(prefix="erc-refmgr-")
pdf_root = os.path.join(tmp, "Library.Data", "PDF", "ab")
os.makedirs(pdf_root)
pdf1 = os.path.join(pdf_root, "Chetty-2009.pdf")
pdf2 = os.path.join(tmp, "autor.pdf")
for p in (pdf1, pdf2):
    with open(p, "wb") as fh:
        fh.write(b"%PDF-1.4 test " + os.path.basename(p).encode())

RIS = "\r\n".join([
    "TY  - JOUR", "AU  - Chetty, Raj", "AU  - Looney, Adam", "AU  - Kroft, Kory", "PY  - 2009///",
    "TI  - Salience and Taxation: Theory and Evidence", "JO  - American Economic Review", "VL  - 99", "IS  - 4",
    "SP  - 1145", "EP  - 1177", "DO  - 10.1257/aer.99.4.1145", "AB  - We show that salience matters.",
    "KW  - tax salience", "KW  - behavioral", "L1  - internal-pdf://1234/Chetty-2009.pdf", "ID  - 17", "ER  - ", "",
    "TY  - JOUR", "AU  - 张三", "AU  - 李四", "PY  - 2024", "TI  - 数字化征管与企业税收遵从", "JO  - 经济研究", "ER  - ", "",
    "TY  - STAT", "TI  - Some Tax Act", "PY  - 2018", "ER  - ", ""])
ris_path = os.path.join(tmp, "endnote.ris")
with open(ris_path, "w", encoding="utf-8", newline="") as fh:
    fh.write(RIS)

esc = pdf2.replace("\\", "\\\\").replace(":", "\\:")
BIB = r"""@comment{jabref-meta: x}
@article{Autor2013,
  title = {The {China} Syndrome: Local Labor Market Effects of Import Competition in the {United States}},
  author = {Autor, David H. and Dorn, David and Hanson, Gordon H.},
  year = {2013}, journal = {American Economic Review}, doi = {10.1257/aer.103.6.2121},
  file = {Full Text PDF:%s:application/pdf;Snapshot:x.html:text/html},
  keywords = {trade, labor}
}
@book{angrist2009,
  title = "Mostly Harmless " # "Econometrics",
  author = {Angrist, Joshua D. and Pischke, J{\"o}rn-Steffen},
  publisher = {Princeton University Press}, year = 2009
}
@article{dupe, title = {Salience and Taxation: Theory and Evidence}, author = {Chetty, Raj}, year = {2009}}
""" % esc
bib_path = os.path.join(tmp, "zotero.bib")
with open(bib_path, "w", encoding="utf-8") as fh:
    fh.write(BIB)

CSL = [{"id": "ABCD1234", "type": "article-journal", "title": "Minimum Wages and Employment: A Case Study of the Fast-Food Industry",
        "author": [{"family": "Card", "given": "David"}, {"family": "Krueger", "given": "Alan B."}],
        "issued": {"date-parts": [[1994]]}, "container-title": "American Economic Review", "DOI": "10.1257/aer.84.4.772"},
       {"id": "EFGH5678", "type": "article-journal", "title": "The China Syndrome: Local Labor Market Effects of Import Competition in the United States",
        "author": [{"family": "Autor", "given": "David"}], "issued": {"date-parts": [[2013]]}, "DOI": "https://doi.org/10.1257/AER.103.6.2121"}]
csl_path = os.path.join(tmp, "zotero.json")
with open(csl_path, "w", encoding="utf-8") as fh:
    json.dump(CSL, fh)

print("[A] parsers")
tb = refmgr.parse_bibtex('@string{x = "y"}\n@article{k1, title = "A {B} c" # " d", year = 2020, author={O{\\"}brien, Tim}}\n@misc{k2,\n title={Q}}')
check(len(tb) == 2 and tb[0]["title"] == "A B c d" and tb[0]["year"] == "2020", "BibTeX: quoted + concatenation + bare year + @string skipped")
tb_paren = refmgr.parse_bibtex('@comment(ignore @article{fake, title={X}})\n@string(j = "AER")\n@article{k3, title={Real Paper}, year={2021}}')
check(len(tb_paren) == 1 and tb_paren[0]["title"] == "Real Paper", "BibTeX: parenthesized @comment/@string skipped cleanly")
check(refmgr.clean('J{\\"o}rn \\& {\\\'E}mile') == "Jörn & Émile", "BibTeX: LaTeX accents and escapes cleaned")
check(refmgr.parse_bib_files("Full Text PDF:C\\:\\\\a\\\\b.pdf:application/pdf;:rel/x.pdf:PDF") == ["C:\\a\\b.pdf", "rel/x.pdf"], "BibTeX file field: Zotero and JabRef forms")
check(refmgr.norm_author("Chetty, Raj") == "Raj Chetty" and refmgr.norm_author("张三") == "张三", "authors: 'Last, First' -> 'First Last'; CJK untouched")
check(refmgr.norm_doi("https://doi.org/10.1257/AER.99.4.1145") == "10.1257/aer.99.4.1145", "DOI normalisation")
check(refmgr.decode_bytes("数字化 税".encode("gb18030")) == "数字化 税", "GBK export decodes")

print("[B] import EndNote RIS")
c, o = pt(VAULT, "cite", "import", ris_path, "--attach", "--pdf-dir", os.path.join(tmp, "Library.Data"), "--dry-run")
check(c == 0 and "[dry-run]" in o and "导入 2 条" in o, "dry-run reports what it would import")
check(not os.path.exists(os.path.join(VAULT, "Meta", "citation-map.json")) and not os.path.exists(os.path.join(VAULT, "03-Literature", "chetty2009salience.md")), "dry-run writes nothing (no map, no note)")
c, o = pt(VAULT, "cite", "import", ris_path, "--attach", "--pdf-dir", os.path.join(tmp, "Library.Data"))
E = cmap(VAULT)
check(c == 0 and "chetty2009salience" in E, "RIS: EndNote numeric ID replaced by chetty2009salience")
check(E["chetty2009salience"]["authors"] == ["Raj Chetty", "Adam Looney", "Kory Kroft"] and E["chetty2009salience"]["year"] == "2009", "RIS: authors and year normalised")
check(E["chetty2009salience"]["status"] == "unverified" and E["chetty2009salience"]["doi"] == "10.1257/aer.99.4.1145", "RIS: starts unverified, DOI kept")
zh = [k for k, v in E.items() if v["type"] == "chinese"]
check(len(zh) == 1 and zh[0].startswith("zh2024") and E[zh[0]]["status"] == "manual", "RIS: Chinese item -> type chinese, status manual")
check("法规类条目" in o and len(E) == 2, "RIS: statute item skipped with instruction")
note = os.path.join(VAULT, "03-Literature", "chetty2009salience.md")
txt = open(note, encoding="utf-8").read() if os.path.exists(note) else ""
check("cite_key: chetty2009salience" in txt and "verification: unverified" in txt and "We show that salience matters." in txt, "RIS: literature note created with abstract")
srcpdf = os.path.join(VAULT, "03-Literature", "_sources", "chetty2009salience.pdf")
check(os.path.isfile(srcpdf) and "sources: [03-Literature/_sources/chetty2009salience.pdf]" in txt and re.search(r'sha256: "[0-9a-f]{64}"', txt) is not None, "RIS: PDF found via --pdf-dir, copied to _sources, sha256 in note")
check(open(pdf1, "rb").read() == open(srcpdf, "rb").read() and os.path.isfile(pdf1), "attachment copied, original left in place")
c, o = pt(VAULT, "cite", "import", ris_path)
check(c == 0 and "导入 0 条（跳过重复 2" in o, "re-import: duplicates skipped by DOI/title")
c, o = pt(VAULT, "cite", "import", ris_path, "--replace", "--no-notes")
check(c == 0 and "已覆盖" in o and len(cmap(VAULT)) == 2, "--replace overwrites without creating extra entries")

print("[C] import Zotero BibTeX and CSL-JSON")
c, o = pt(VAULT, "cite", "import", bib_path, "--attach")
E = cmap(VAULT)
check(c == 0 and "Autor2013" in E and "angrist2009" in E, "BibTeX: valid imported keys kept")
check(E["Autor2013"]["title"].startswith("The China Syndrome:") and "{" not in E["Autor2013"]["title"], "BibTeX: braces removed from title")
check(E["angrist2009"]["type"] == "book" and E["angrist2009"]["title"] == "Mostly Harmless Econometrics" and "Jörn-Steffen Pischke" in E["angrist2009"]["authors"], "BibTeX: @book, # concatenation, accents")
check("重复" in o and "dupe" not in E, "BibTeX: duplicate of an EndNote record skipped")
check(os.path.isfile(os.path.join(VAULT, "03-Literature", "_sources", "Autor2013.pdf")), "BibTeX: escaped Windows file path resolved and copied")
c, o = pt(VAULT, "cite", "import", csl_path)
E = cmap(VAULT)
check(c == 0 and "card1994minimum" in E, "CSL: Zotero item key replaced by authorYEARword key")
check(not any(k in ("ABCD1234", "EFGH5678") for k in E) and len(E) == 5, "CSL: DOI duplicate (URL form, upper case) skipped")

print("[D] lint, index and bridge")
lint = os.path.join(os.path.dirname(PT), "wiki_lint.py")
idx = open(os.path.join(VAULT, "Meta", "index.md"), encoding="utf-8").read()
check("[[chetty2009salience]]" in idx and "[[Autor2013]]" in idx and idx.count("[[chetty2009salience]]") == 1, "notes registered once in Meta/index.md (文献 table)")
check("参考文献软件导入" in open(os.path.join(VAULT, "Meta", "log.md"), encoding="utf-8").read(), "Meta/log.md entry appended")
subprocess.run([sys.executable, "-X", "utf8", lint, "map", "--vault", VAULT], capture_output=True)
r = subprocess.run([sys.executable, "-X", "utf8", lint, "lint", "--vault", VAULT], capture_output=True, text=True, encoding="utf-8")
check("0 error(s)" in r.stdout and "0 warning(s)" in r.stdout, "wiki_lint: imported notes, index and _sources links give 0 errors, 0 warnings")
c, o = pt(VAULT, "cite", "from-note", os.path.join("03-Literature", "chetty2009salience.md"), "--replace")
check(c == 0 and "chetty2009salience" in o, "imported note bridges back through cite from-note")

print("[E] export")
ris_out, csl_out, bib_out = (os.path.join(tmp, n) for n in ("out.ris", "out.json", "out.bib"))
c1, _ = pt(VAULT, "cite", "ris", "-o", ris_out)
c2, _ = pt(VAULT, "cite", "csl", "-o", csl_out)
c3, _ = pt(VAULT, "cite", "bib", "-o", bib_out)
rt = open(ris_out, "rb").read()
check(c1 == 0 and rt.startswith(b"\xef\xbb\xbf") and b"TY  - JOUR" in rt and b"ER  - " in rt, "RIS export: BOM + TY/ER records")
check(b"SP  - 1145" in rt and b"EP  - 1177" in rt, "RIS export: page range split into SP and EP")
cj = json.load(open(csl_out, encoding="utf-8"))
check(c2 == 0 and len(cj) == 5 and any(x.get("author", [{}])[0].get("literal") == "张三" for x in cj) and any(x["id"] == "card1994minimum" and x["author"][0]["family"] == "Card" for x in cj), "CSL export: names split, CJK literal")
check(c3 == 0 and "abstract = {We show that salience matters.}" in open(bib_out, encoding="utf-8").read(), "BibTeX export carries abstract/keywords")
check("pages = {1145--1177}" in open(bib_out, encoding="utf-8").read() and "----" not in open(bib_out, encoding="utf-8").read(), "BibTeX export normalises page dashes to -- without quadrupling")
v2 = os.path.join(tmp, "vault2")
os.makedirs(os.path.join(v2, "Meta")); os.makedirs(os.path.join(v2, "01-Research-Projects"))
c, o = pt(v2, "cite", "import", ris_out, "--no-notes")
E1, E2 = cmap(VAULT), cmap(v2)
check(c == 0 and len(E2) == 5 and {e["doi"] for e in E1.values() if e["doi"]} == {e["doi"] for e in E2.values() if e["doi"]}, "round trip: exported RIS re-imports with the same DOIs")
check({e["title"] for e in E1.values()} == {e["title"] for e in E2.values()}, "round trip: titles identical (incl. Chinese)")
gbk = os.path.join(tmp, "gbk.ris")
open(gbk, "wb").write("TY  - JOUR\r\nTI  - 平台经济与税收治理\r\nAU  - 王五\r\nPY  - 2023\r\nER  - \r\n".encode("gb18030"))
c, o = pt(v2, "cite", "import", gbk, "--no-notes")
check(c == 0 and any("平台经济" in e["title"] for e in cmap(v2).values()), "GBK-encoded EndNote export imports correctly")

print("[F] Zotero API")
SERVED = []


ITEM = {"id": "ZZZZ9999", "type": "article-journal", "title": "Tax Evasion and Inequality",
        "author": [{"family": "Alstadsæter", "given": "Annette"}], "issued": {"date-parts": [[2019]]}, "DOI": "10.1257/aer.20172043"}
POSTED = []


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        SERVED.append((self.command, self.path, self.headers.get("Zotero-API-Key"), self.headers.get("Zotero-API-Version")))
        if "/children" in self.path:
            return self._send([{"data": {"itemType": "note", "note": "<p>Key point: <b>salience</b> matters.</p>"}}])
        if "/items/ZZZZ9999" in self.path and "/top" not in self.path:
            return self._send({"items": [ITEM]})
        self._send({"items": [ITEM] if "start=0" in self.path or "q=" in self.path else []})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        POSTED.append((self.path, self.headers.get("Zotero-API-Key"), self.headers.get("Zotero-Write-Token"), json.loads(self.rfile.read(n))))
        self._send({"successful": {"0": {"key": "NOTE0001"}}, "failed": {}})

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/api/users/0" % srv.server_port
c, o = pt(v2, "cite", "zotero", "--base-url", base, env={"ZOTERO_API_KEY": "secret-test-key"})
E2 = cmap(v2)
check(c == 0 and any(e["doi"] == "10.1257/aer.20172043" for e in E2.values()), "zotero: items pulled and imported as unverified")
check(SERVED and all(s[0] == "GET" for s in SERVED) and "/items/top?format=csljson" in SERVED[0][1] and SERVED[0][3] == "3", "zotero: read-only GET against /items/top (csljson, API v3)")
check("secret-test-key" not in o, "zotero: API key never printed")
c, o = pt(v2, "cite", "zotero", "--base-url", base, "--query", "tax evasion", "--list")
check(c == 0 and "ZZZZ9999" in o and any("q=tax%20evasion" in x[1] for x in SERVED), "zotero --query --list: searches without importing")
c, o = pt(v2, "cite", "zotero", "--base-url", base, "--item", "ZZZZ9999", "--notes", "--replace")
E2 = cmap(v2)
zk = [k for k, e in E2.items() if e.get("zotero_key") == "ZZZZ9999"]
note2 = os.path.join(v2, "03-Literature", zk[0] + ".md") if zk else ""
check(c == 0 and zk, "zotero --item: single item pulled, Zotero item key recorded")
check(note2 and "## Zotero 笔记" in open(note2, encoding="utf-8").read() and "salience matters" in open(note2, encoding="utf-8").read(), "zotero --notes: child notes appended as read-only quote")
check(all(s_[0] == "GET" for s_ in SERVED), "zotero pulls still GET only")
if zk:
    with open(note2, "a", encoding="utf-8") as fh:
        fh.write("\n# 一、研究问题与定位\n逃税与不平等的测度。\n")
c, o = pt(v2, "cite", "zotero-note", zk[0], "--base-url", base)
check(c == 0 and "[dry-run]" in o and not POSTED, "zotero-note: preview only without --yes")
c, o = pt(v2, "cite", "zotero-note", zk[0], "--base-url", base, "--yes", env={"ZOTERO_API_KEY": "wkey"})
check(c == 0 and len(POSTED) == 1 and POSTED[0][0].endswith("/items") and POSTED[0][3][0]["parentItem"] == "ZZZZ9999" and POSTED[0][3][0]["itemType"] == "note", "zotero-note --yes: one new child note POSTed")
check(POSTED and "逃税与不平等" in POSTED[0][3][0]["note"] and "erc:cite_key=" in POSTED[0][3][0]["note"] and POSTED[0][1] == "wkey" and POSTED[0][2], "zotero-note: content, marker, key and write token sent")
c, o = pt(v2, "cite", "zotero-note", zk[0], "--user", "1", "--yes", env={"ZOTERO_API_KEY": "wkey", "ERC_OFFLINE": "1"})
check(c != 0 and len(POSTED) == 1, "zotero-note: blocked by ERC_OFFLINE for the web API")
c, o = pt(v2, "cite", "open", "nokey", "--print")
check(c != 0, "cite open: unknown key rejected")
c, o = pt(VAULT, "cite", "open", "chetty2009salience", "--print")
check(c == 0 and o.strip().endswith("chetty2009salience.pdf"), "cite open --print: resolves the PDF in _sources")
c, o = pt(v2, "cite", "zotero", "--base-url", "http://example.com/api/users/1")
check(c != 0 and "https" in o, "zotero: refuses plain http to a non-local host")
c, o = pt(v2, "cite", "zotero", "--user", "1")
check(c != 0 and "--offline" in o, "zotero: ERC_OFFLINE blocks the web API")

print("[G] colon keys & --replace preservation")
colon_pdf = os.path.join(tmp, "colon.pdf")
with open(colon_pdf, "wb") as fh:
    fh.write(b"%PDF-1.4 colon")
colon_bib = os.path.join(tmp, "colon.bib")
with open(colon_bib, "w", encoding="utf-8") as fh:
    fh.write('@article{tax:2024, title={Colon Key Test}, author={Doe, Jane}, year={2024}, file={PDF:%s:application/pdf}}\n' % colon_pdf.replace("\\", "\\\\").replace(":", "\\:"))
c, o = pt(VAULT, "cite", "import", colon_bib, "--attach")
check(c == 0 and "tax:2024" in cmap(VAULT), "colon key: imported into citation-map")
c_open, o_open = pt(VAULT, "cite", "open", "tax:2024", "--print")
check(c_open == 0 and o_open.strip().endswith("tax_2024.pdf"), "colon key: cite open resolves sanitized PDF")
idx_after = open(os.path.join(VAULT, "Meta", "index.md"), encoding="utf-8").read()
check("[[tax_2024]]" in idx_after and "[[tax:2024]]" not in idx_after, "colon key: Meta/index.md links to sanitized note stem")
subprocess.run([sys.executable, "-X", "utf8", lint, "map", "--vault", VAULT], capture_output=True)
r_col = subprocess.run([sys.executable, "-X", "utf8", lint, "lint", "--vault", VAULT], capture_output=True, text=True, encoding="utf-8")
check("0 error(s)" in r_col.stdout and "0 warning(s)" in r_col.stdout, "colon key: wiki_lint passes with 0 errors and 0 warnings")
# verify --replace keeps zotero_key and locator
if zk:
    c_fn, _ = pt(v2, "cite", "from-note", os.path.join("03-Literature", zk[0] + ".md"), "--replace")
    check(c_fn == 0 and cmap(v2)[zk[0]].get("zotero_key") == "ZZZZ9999", "cite from-note --replace preserves zotero_key")
c_add, _ = pt(VAULT, "cite", "add", "--key", "tax:2024", "--title", "Colon Key Test", "--year", "2024", "--locator", "p.10", "--replace")
c_imp2, _ = pt(VAULT, "cite", "import", colon_bib, "--replace", "--no-notes")
check(c_imp2 == 0 and cmap(VAULT)["tax:2024"].get("locator") == "p.10", "cite import --replace preserves existing locator")

srv.shutdown()
print("selftest failures: %d" % fails)
sys.exit(1 if fails else 0)
