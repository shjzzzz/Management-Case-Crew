#!/usr/bin/env python3
"""PostToolUse hook: sanity-check YAML frontmatter of Markdown files just written.

Checks: closing '---' present, no tab characters in frontmatter. The write has
already happened, so this cannot undo it; exit 2 only feeds the message back
to Claude so it can fix the file. Skips .claude/ and non-.md files. Fails open.
"""
import json
import os
import sys


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace"))  # UTF-8 regardless of locale
    except Exception:
        sys.exit(0)
    ti = data.get("tool_input", {}) or {}
    fp = ti.get("file_path", "") or ""
    if not fp.lower().endswith(".md"):
        sys.exit(0)
    n = fp.replace("\\", "/")
    if "/.claude/" in n or n.startswith(".claude/"):
        sys.exit(0)
    cwd = data.get("cwd") or os.getcwd()
    path = fp if os.path.isabs(fp) else os.path.join(cwd, fp)
    if not os.path.isfile(path):
        sys.exit(0)
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        sys.exit(0)
    if not lines or lines[0].strip() != "---":
        sys.exit(0)
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        sys.stderr.write("WARNING: frontmatter in %s has no closing '---'; Obsidian will not parse it. Please fix.\n" % os.path.basename(path))
        sys.exit(2)
    for i in range(1, end):
        if "\t" in lines[i]:
            sys.stderr.write("WARNING: frontmatter in %s line %d contains a tab; YAML needs spaces. Please fix.\n" % (os.path.basename(path), i + 1))
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
