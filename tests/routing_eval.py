#!/usr/bin/env python3
"""Routing evaluation for Economics Research Crew (uses Claude Code quota!).

Installs nothing itself: point --vault at a THROWAWAY vault where the Crew is
already installed. The script adds .claude/settings.local.json with a logging
hook that records every tool call; Task/Agent dispatches are recorded and then
blocked so subagents never actually run (keeps cost bounded). It refuses to
touch a vault that already has settings.local.json; the hook files are removed on exit.

Usage:
    python tests/routing_eval.py --vault <temp vault> [--model claude-opus-5-5]
                                 [--only id1,id2] [--max-turns 4] [--out DIR]

Each case runs in a fresh headless session, sequentially (no concurrency).
Web tools are disabled (routing is decided before any research); each case is
killed with its whole process tree after --timeout seconds.
PASS when the first routing action (Skill or subagent) is in `expect`;
"direct" means no Skill/subagent was used.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

LOGGER = r'''import json, os, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
log = os.environ.get("ERC_ROUTING_LOG") or os.path.join(d.get("cwd", "."), ".claude", "routing.log")
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps({"tool": d.get("tool_name"), "input": d.get("tool_input")}, ensure_ascii=False) + "\n")
if d.get("tool_name") in ("Task", "Agent"):
    sys.stderr.write("ROUTING TEST: subagent dispatch recorded and intentionally not executed. "
                     "Do not retry or work around; briefly state what that agent would do and stop.\n")
    sys.exit(2)
sys.exit(0)
'''


def kill_tree(pid):
    """Kill a process and all its children (claude spawns helpers; plain kill leaves them running)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except Exception:
            pass


def routes_from_log(path):
    routes, writes = [], []
    if not path.exists():
        return routes, writes
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        tool, ti = e.get("tool"), e.get("input") or {}
        if tool == "Skill":
            name = str(ti.get("skill") or ti.get("command") or "").lstrip("/")
            routes.append("skill:" + name)
        elif tool in ("Task", "Agent"):
            routes.append("agent:" + str(ti.get("subagent_type") or ti.get("agent") or "general-purpose"))
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            writes.append(str(ti.get("file_path") or ti.get("notebook_path") or ""))
        elif tool in ("Bash", "PowerShell"):
            writes.append("$ " + str(ti.get("command", ""))[:200])
    return routes, writes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--cases", default=str(HERE / "routing_cases.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    vault = Path(a.vault).resolve()
    claude_dir = vault / ".claude"
    local = claude_dir / "settings.local.json"
    if not (claude_dir / "MANAGEMENT-CASE-RESEARCH.md").exists():
        sys.exit("vault does not look like an installed Crew vault: " + str(vault))
    if local.exists() and "routing_logger" not in local.read_text(encoding="utf-8", errors="replace"):
        sys.exit("refusing: %s already exists (use a throwaway vault)" % local)
    logger = claude_dir / "routing_logger.py"
    logger.write_text(LOGGER, encoding="utf-8")
    local.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR/.claude/routing_logger.py"'}]}]}}, indent=2), encoding="utf-8")

    try:
        return run_cases(a, vault)
    finally:
        # always remove the test-only hook so the vault is never left with blocked subagents
        for f in (local, logger):
            try:
                f.unlink()
            except FileNotFoundError:
                pass


def run_cases(a, vault):
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    out = Path(a.out) if a.out else vault / "_routing_results"
    out.mkdir(parents=True, exist_ok=True)
    claude = shutil.which("claude") or "claude"
    results = []
    for c in cases:
        log = out / ("%s.log" % c["id"])
        if log.exists():
            log.unlink()
        env = dict(os.environ, ERC_ROUTING_LOG=str(log))
        t0 = time.time()
        cmd = [claude, "-p", c["prompt"], "--model", a.model, "--max-turns", str(a.max_turns),
               "--output-format", "json", "--disallowedTools", "WebSearch,WebFetch"]
        proc = subprocess.Popen(cmd, cwd=str(vault), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding="utf-8", errors="replace")
        timed_out = False
        try:
            raw, _ = proc.communicate(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_tree(proc.pid)
            raw, _ = proc.communicate()
        answer = ""
        try:
            data = json.loads(raw)
            events = data if isinstance(data, list) else [data]
            for e in events:
                if e.get("type") == "result":
                    answer = e.get("result") or ""
        except ValueError:
            answer = raw[-2000:]
        (out / ("%s.answer.md" % c["id"])).write_text(answer, encoding="utf-8")
        routes, writes = routes_from_log(log)
        first = routes[0] if routes else "direct"
        ok = first in c["expect"]
        notes = []
        for prefix in c.get("forbid_write_under", []):
            bad = [w for w in writes if prefix.replace("/", "\\") in w or prefix in w.replace("\\", "/")]
            bad = [w for w in bad if not w.startswith("$ ") or any(k in w for k in (" rm ", ">", "Remove-Item", "mv "))]
            if bad:
                ok = False
                notes.append("write to forbidden path: %s" % bad[:2])
        if timed_out:
            notes.append("timed out after %ds (process tree killed)" % a.timeout)
        if "max_parallel_agents" in c:
            n_agents = sum(1 for r in routes if r.startswith("agent:"))
            if n_agents > c["max_parallel_agents"]:
                ok = False
                notes.append("dispatched %d agents" % n_agents)
        results.append({"id": c["id"], "pass": ok, "first": first, "routes": routes, "expect": c["expect"],
                        "notes": notes, "seconds": round(time.time() - t0)})
        print("%-13s %s  first=%-32s routes=%s %s" % (c["id"], "PASS" if ok else "FAIL", first, routes, "; ".join(notes)), flush=True)
    (out / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(r["pass"] for r in results)
    print("passed %d/%d  results: %s" % (passed, len(results), out))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
