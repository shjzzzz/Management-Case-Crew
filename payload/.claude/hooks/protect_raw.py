#!/usr/bin/env python3
"""PreToolUse hook: protect immutable raw material.

Blocks (exit 2) modification of anything under 06-Data/raw and
03-Literature/_sources. Creating a NEW file via Write is allowed (importing
new raw material); overwriting/editing/deleting existing files is blocked.

Limits (be honest): Write/Edit/MultiEdit/NotebookEdit are checked exactly.
Bash and PowerShell tool commands are checked heuristically (destructive verbs, redirects, copy-to-dest
that mention a protected path); it cannot catch every shell construct.
Fails open (exit 0) on malformed hook input.

Also runs as an Antigravity (agy) PreToolUse hook: input has `toolCall`
(write_file/edit_file/run_command); output is JSON `decision` deny/ask.
"""
import json
import os
import re
import sys

PROTECTED = ["06-data/raw", "03-literature/_sources"]
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
DESTRUCTIVE = re.compile(
    r"(?i)(?:^|[\s;&|(])(rm|rmdir|mv|move|del|erase|ren|rename|truncate|shred|"
    r"remove-item|move-item|rename-item|set-content|add-content|clear-content|out-file|tee)\b"
    r"|sed\s+-[a-z]*i"
)
COPYLIKE = re.compile(r"(?i)(?:^|[\s;&|(])(cp|copy|xcopy|robocopy|copy-item)\b")
REDIRECT = re.compile(r"(?:^|[^<\d])>>?\s*[\"']?([^\s\"'|;&]+)")


def norm(p):
    # unify separators and collapse repeats ("06-Data\\raw", "06-Data//raw")
    return re.sub(r"/+", "/", p.replace("\\", "/")).lower()


def is_protected(path):
    n = norm(path)
    return any(("/" + pr + "/") in ("/" + n + "/") or n.startswith(pr + "/") or n.endswith("/" + pr)
               or ("/" + pr + "/") in n for pr in PROTECTED)


AGY = False  # set when the input comes from Antigravity (agy) instead of Claude Code
# agy tool names / argument keys (confirmed by a live PreToolUse probe) -> Claude equivalents
AGY_TOOLS = {"write_file": ("Write", "Path", "file_path"), "edit_file": ("Edit", "Path", "file_path"),
             "run_command": ("Bash", "CommandLine", "command")}


def done():
    # agy expects JSON on stdout; "ask" keeps its normal permission flow ("allow" would auto-approve)
    if AGY:
        sys.stdout.write('{"decision":"ask"}\n')
    sys.exit(0)


def block(msg):
    if AGY:
        sys.stdout.write(json.dumps({"decision": "deny", "reason": "BLOCKED by protect_raw hook: " + msg}) + "\n")
        sys.exit(0)
    sys.stderr.write("BLOCKED by protect_raw hook: " + msg + "\n")
    sys.exit(2)


def normalize(data):
    """Return (tool, tool_input) in Claude Code terms for either host."""
    global AGY
    if "toolCall" in data:
        AGY = True
        tc = data.get("toolCall") or {}
        args = tc.get("args") or {}
        name, src_key, dst_key = AGY_TOOLS.get(tc.get("name", ""), ("", "", ""))
        return name, ({dst_key: args.get(src_key, "")} if name else {})
    return data.get("tool_name", ""), (data.get("tool_input", {}) or {})


def main():
    global AGY
    raw = ""
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")  # hosts send UTF-8; Windows python would decode as GBK
        data = json.loads(raw)
        tool, ti = normalize(data)
    except Exception:
        AGY = '"toolCall"' in raw  # agy still needs a JSON answer when its input is unreadable
        done()
    cwd = data.get("cwd") or os.getcwd()

    if tool in FILE_TOOLS:
        fp = ti.get("file_path") or ti.get("notebook_path") or ""
        if not fp:
            done()
        absp = os.path.normpath(fp if os.path.isabs(fp) else os.path.join(cwd, fp))
        if is_protected(absp):
            if tool == "Write" and not os.path.exists(absp):
                done()
            block("%s targets immutable raw material (%s). Raw data/sources are read-only; "
                  "write derived output to 06-Data/processed or a note instead." % (tool, fp))
        done()

    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "") or ""
        n = norm(cmd)
        if not any(pr in n for pr in PROTECTED):
            done()
        if DESTRUCTIVE.search(cmd):
            # only block when a protected path is part of the same command
            block("command appears to modify/delete files and mentions a protected raw path.")
        for m in REDIRECT.finditer(cmd):
            if is_protected(m.group(1)):
                block("shell redirect writes into a protected raw path.")
        if COPYLIKE.search(cmd):
            tokens = cmd.strip().split()
            if tokens and is_protected(tokens[-1].strip("\"'")):
                block("copy destination is a protected raw path.")
    done()


if __name__ == "__main__":
    main()
