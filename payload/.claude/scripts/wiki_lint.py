#!/usr/bin/env python3
"""Deterministic wiki checks for the Economics Research Crew vault.

Usage:
    python wiki_lint.py lint [--vault PATH] [--json] [--strict]
    python wiki_lint.py hash FILE [--vault PATH]

lint  : frontmatter, sources[] resolvability, broken wikilinks, orphan pages,
        index coverage. Scope = new research folders only (legacy tax-law
        notes are never scanned).
hash  : print SHA256 of FILE and report whether Meta/source-registry.md
        already contains it (exit 10 if already registered).

Exit codes: 0 ok, 1 errors found (or warnings with --strict), 10 hash already registered.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCOPE = ["01-Research-Projects", "03-Literature", "04-Theories",
         "05-Methods", "08-Research-Notes", "09-Writing"]
SKIP_PARTS = {"_sources", ".obsidian", ".claude", ".agents", ".codex", ".git", "node_modules",
              "_vendor", "_erc-staging", "_erc-backups", "Templates"}
NEEDS_SOURCES = {"literature", "theory", "method", "synthesis", "query"}
PATH_EXT = (".pdf", ".md", ".txt", ".csv", ".dta", ".xlsx", ".html", ".epub", ".docx")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


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


def md_files(root, dirs=None):
    bases = [root / d for d in dirs] if dirs else [root]
    for base in bases:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            rel = p.relative_to(root)
            if any(part in SKIP_PARTS or part.startswith("_erc") for part in rel.parts):
                continue
            yield p


def looks_like_path(s):
    return ("/" in s or "\\" in s or s.lower().endswith(PATH_EXT)) and not re.match(r"^(https?:|doi:|10\.\d)", s, re.I)


def lint(vault, strict=False):
    findings = []

    def add(level, page, check, msg):
        findings.append({"level": level, "file": str(page), "check": check, "msg": msg})

    scope_pages = sorted(md_files(vault, SCOPE))
    all_pages = list(md_files(vault))
    stems = {}
    for p in all_pages:
        stems.setdefault(p.stem.lower(), []).append(p)

    index = vault / "Meta" / "index.md"
    index_text = read(index) if index.exists() else None
    if index_text is None:
        add("warning", "Meta/index.md", "index", "Meta/index.md not found; index coverage not checked")

    inbound = {p: set() for p in scope_pages}
    index_targets = set()
    if index_text:
        index_targets = {m.group(1).strip().split("/")[-1].lower() for m in WIKILINK.finditer(index_text)}

    for p in scope_pages:
        rel = p.relative_to(vault).as_posix()
        text = read(p)
        fm, err = parse_frontmatter(text)
        if err:
            add("error", rel, "frontmatter", err)
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
        for m in WIKILINK.finditer(text):
            target = m.group(1).strip().replace("\\", "/").split("/")[-1]
            if target.lower().endswith(".md"):
                target = target[:-3]
            if not stems.get(target.lower()):
                add("error", rel, "link", "broken wikilink [[%s]]" % m.group(1).strip())
        if index_text is not None and p.stem.lower() not in index_targets:
            add("warning", rel, "index", "not listed in Meta/index.md")

    # inbound links may come from any page in the vault (index, MOC, notes), not only scope pages
    scope_set = set(scope_pages)
    for src in all_pages:
        try:
            src_text = read(src)
        except OSError:
            continue
        for m in WIKILINK.finditer(src_text):
            target = m.group(1).strip().replace("\\", "/").split("/")[-1]
            if target.lower().endswith(".md"):
                target = target[:-3]
            for h in stems.get(target.lower(), []):
                if h in scope_set and h != src:
                    inbound[h].add(src)

    for p, srcs in inbound.items():
        if not srcs:
            add("warning", p.relative_to(vault).as_posix(), "orphan", "no inbound links from any page (index, MOC or notes)")

    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    return findings, len(scope_pages), errors, warnings


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
    ph = sub.add_parser("hash")
    ph.add_argument("file")
    ph.add_argument("--vault", default=".")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    if a.cmd == "hash":
        return cmd_hash(vault, a.file)
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
