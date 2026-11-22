#!/usr/bin/env python3
"""PostToolUse hook: check a paper draft right after it is written (Claude Code).

Applies to Markdown files under 01-Research-Projects/<project>/paper/. Feeds back (exit 2, stderr) when
  - a citation key [@key] is not in Meta/citation-map.json            (invented or mistyped reference)
  - a {{res:id}} placeholder is not in Meta/results-ledger.json       (invented or mistyped result)
Self-contained & lightweight: avoids importing paper_tools.py or hashing source files on the hot path.
Unverified-but-registered citations and bare statistics are reported by `paper_tools.py cite/results check`.
Fails open.
"""
import json
import os
import re
import sys

CODE_FENCE = re.compile(r"```.*?```", re.S)
CITE_GROUP = re.compile(r"\[([^\[\]]*@[^\[\]]*)\]")
CITE_KEY = re.compile(r"@([A-Za-z][A-Za-z0-9_:\-]*)")
PLACEHOLDER = re.compile(r"\{\{res:([A-Za-z0-9_.\-:]+?)(?::(\d+))?\}\}")


def find_vault(start):
    d = os.path.abspath(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, "Meta")) and os.path.isdir(os.path.join(d, "01-Research-Projects")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_entries(path):
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8-sig") as fh:
        return (json.load(fh) or {}).get("entries", {})


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace"))
        fp = ((data.get("tool_input") or {}).get("file_path") or "")
        nl = fp.replace("\\", "/").lower()
        if (not nl.endswith(".md") or "/paper/" not in nl or "01-research-projects/" not in nl
                or "/paper/versions/" in nl or os.path.basename(nl).startswith("worklog-")):
            return
        cwd = data.get("cwd") or os.getcwd()
        vault = find_vault(cwd)
        path = fp if os.path.isabs(fp) else os.path.join(cwd, fp)
        if not vault or not os.path.isfile(path):
            return
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            text = CODE_FENCE.sub("", fh.read())
        rel = os.path.relpath(path, vault).replace("\\", "/")
        c_entries = load_entries(os.path.join(vault, "Meta", "citation-map.json"))
        r_entries = load_entries(os.path.join(vault, "Meta", "results-ledger.json"))
        c_errs = sorted({
            "%s：引用键 @%s 不在引文表中" % (rel, k)
            for grp in CITE_GROUP.findall(text)
            for k in CITE_KEY.findall(grp)
            if k not in c_entries
        })
        r_errs = sorted({
            "%s：{{res:%s}} 不在结果登记簿中" % (rel, mo.group(1))
            for mo in PLACEHOLDER.finditer(text)
            if mo.group(1) not in r_entries
        })
        problems = c_errs + r_errs
    except Exception:
        return
    if problems:
        msg = "WARNING（草稿已写入，请修正）：\n" + "\n".join("  - " + p for p in problems[:8]) + \
              "\n只能引用 Meta/citation-map.json 里的键、使用 Meta/results-ledger.json 里的结果；不要编造。\n"
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
        sys.exit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
