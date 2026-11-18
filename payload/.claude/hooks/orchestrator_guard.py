#!/usr/bin/env python3
"""PreToolUse hook: enforce the research orchestration rules (Claude Code).

Matcher: Agent|Task|Bash|PowerShell|Write|Edit|MultiEdit

1. Agent / Task dispatch of a pipeline Agent while a project is active:
   - blocked when the agent belongs to a LATER stage than the project's current stage
     (no skipping ahead, e.g. no independent review before execution has passed its gate);
   - blocked after the stage's retry budget for that agent is used up;
   - blocked when the stage's parallel limit is reached (default 1, hard cap 3).
   Other agents (Explore, plugins, ...) and dispatches outside an active project are allowed
   (and recorded in the run ledger).
2. `orchestrator.py gate ...` through Bash/PowerShell: forces a permission prompt, so a gate can
   only pass when the researcher confirms it.
3. `paper_tools.py cite confirm ...` (the researcher's manual source verification) also forces a prompt.
4. Direct Write/Edit of STATE.json, run-ledger.jsonl, citation-map.json, results-ledger.json or
   reviews.json is blocked: use orchestrator.py / paper_tools.py.

Fails open: any unexpected error allows the call. `orchestrator.py enforce off` turns blocking off
for a project (the ledger still records).
"""
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

GATE_CMD = re.compile(r"orchestrator\.py[\"']?\s+(?:--\S+\s+\S+\s+)*gate\b")
PROTECTED_FILE = re.compile(r"(?:^|/)(?:STATE\.json|run-ledger\.jsonl|citation-map\.json|results-ledger\.json|reviews\.json)$", re.I)
CONFIRM_CMD = re.compile(r"paper_tools\.py[\"']?\s+(?:--\S+\s+\S+\s+)*cite\s+confirm\b")


def block(msg):
    # Write UTF-8 bytes: on Windows the default stderr codec (GBK) turns the Chinese reason into mojibake
    sys.stderr.buffer.write(("BLOCKED by orchestrator_guard: " + msg + "\n").encode("utf-8"))
    sys.stderr.flush()
    sys.exit(2)


def ask(msg):
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": msg}}) + "\n")
    sys.exit(0)


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace"))
        import orchestrator as orc
        tool = data.get("tool_name", "")
        ti = data.get("tool_input", {}) or {}
        vault = orc.find_vault(data.get("cwd"))
        if not vault:
            return
        cfg = orc.load_cfg()
    except Exception:
        return

    try:
        if tool in ("Write", "Edit", "MultiEdit"):
            fp = (ti.get("file_path") or "").replace("\\", "/")
            if PROTECTED_FILE.search(fp):
                block("%s 由脚本维护，不要直接编辑；用 orchestrator.py / paper_tools.py 的命令。" % os.path.basename(fp))
            return

        if tool in ("Bash", "PowerShell"):
            cmd = ti.get("command", "") or ""
            if GATE_CMD.search(cmd):
                ask("这是研究关卡决定：只有研究者表态后才应通过。请确认研究者已作出该决定（--decision / --note 与其一致）。")
            if CONFIRM_CMD.search(cmd):
                ask("这是研究者对引文来源的人工核验：只有研究者亲自核对原文后才应确认。请确认 --note 如实反映了核对方式。")
            return

        if tool not in ("Agent", "Task"):
            return
        agent = ti.get("subagent_type") or ""
        ap = orc.active_project(vault)
        req_id = uuid.uuid4().hex[:12]
        proj = ap[1] if ap else None
        sid = proj["stage"] if proj else None
        if not proj or not proj.get("enforce", True):
            orc.ledger_append(vault, "dispatch_request", req_id=req_id, agent=agent,
                              project=proj["project"] if proj else None, stage=sid, enforced=False)
            return
        ai = orc.agent_stage_index(cfg, agent)
        if ai < 0:  # not a pipeline agent
            orc.ledger_append(vault, "dispatch_request", req_id=req_id, agent=agent, project=proj["project"], stage=sid)
            return
        ci = orc.stage_index(cfg, sid)
        stage = cfg["stages"][ci]
        if ai > ci:
            block("%s 属于阶段 %s，而项目当前在 %s %s；前序关卡未通过，不能跳阶段。先用 orchestrator.py next 查看。"
                  % (agent, cfg["stages"][ai]["id"], sid, stage["name"]))
        budget = 1 + cfg.get("max_retries", 2)
        n = proj["stages"][sid]["attempts"].get(agent, 0)
        if n >= budget:
            block("%s 在阶段 %s 已失败 %d 次，达到重试上限。停下并向研究者报告；研究者决定 revise 后才可继续。" % (agent, sid, n))
        limit = min(stage.get("max_parallel", 1), cfg.get("max_parallel_cap", 3))
        running = orc.running_dispatches(vault, cfg)
        if len(running) >= limit:
            block("阶段 %s 同时最多 %d 个 Agent，当前已有 %d 个在运行/待启动。等其完成；若是残留记录，运行 orchestrator.py recover。"
                  % (sid, limit, len(running)))
        orc.ledger_append(vault, "dispatch_request", req_id=req_id, agent=agent, project=proj["project"], stage=sid)
    except SystemExit:
        raise
    except Exception:
        return  # fail open


if __name__ == "__main__":
    main()
    sys.exit(0)
