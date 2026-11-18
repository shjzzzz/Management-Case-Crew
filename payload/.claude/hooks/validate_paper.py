#!/usr/bin/env python3
"""PostToolUse hook: check a paper draft right after it is written (Claude Code).

Applies to Markdown files under 01-Research-Projects/<project>/paper/. Feeds back (exit 2, stderr) when
  - a citation key [@key] is not in Meta/citation-map.json            (invented or mistyped reference)
  - a {{res:id}} placeholder is not in Meta/results-ledger.json       (invented or mistyped result)
It only warns: the write has already happened. Unverified-but-registered citations and bare statistics are
reported by `paper_tools.py cite check` / `results check`, not here. Fails open.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace"))
        fp = ((data.get("tool_input") or {}).get("file_path") or "")
        n = fp.replace("\\", "/")
        if not n.lower().endswith(".md") or "/paper/" not in n or "01-Research-Projects/" not in n:
            return
        import paper_tools as pt
        import orchestrator as orc
        vault = orc.find_vault(data.get("cwd"))
        path = fp if os.path.isabs(fp) else os.path.join(data.get("cwd") or os.getcwd(), fp)
        if not vault or not os.path.isfile(path):
            return
        errors, _, _ = pt.cite_problems(vault, [path], strict=False)
        errors = [e for e in errors if "不在引文表中" in e]
        rerrors, _ = pt.results_problems(vault, [path])
        problems = errors + [e for e in rerrors if "不在结果登记簿中" in e]
    except Exception:
        return
    if problems:
        msg = "WARNING（草稿已写入，请修正）：\n" + "\n".join("  - " + p for p in problems[:8]) + \
              "\n只能引用 Meta/citation-map.json 里的键、使用 Meta/results-ledger.json 里的结果；不要编造。\n"
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.flush()
        sys.exit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
