#!/usr/bin/env python3
"""SessionStart hook: inject concise project stage & purpose state into Claude Code.

Fires on session startup, resume, clear and post-compaction (SessionStart). Pure Python
standard library, zero LLM calls, zero child processes; silent when no active project
exists and Meta/purpose.md is already filled. Fails open (exit 0) on any error.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

PURPOSE_PLACEHOLDER = "（一两句话：例如"


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")
        data = json.loads(raw) if raw.strip() else {}
        import orchestrator as orc
        vault = orc.find_vault(data.get("cwd"))
        if not vault:
            return
        lines = []
        ap = orc.active_project(vault)
        if ap:
            _, st = ap
            cfg = orc.load_cfg()
            sid = st.get("stage", "")
            idx = orc.stage_index(cfg, sid)
            if idx >= 0:
                stage = cfg["stages"][idx]
                problems = orc.verify_stage(vault, cfg, st, sid)
                src = data.get("source") or "startup"
                tag = "ERC 压缩后状态恢复" if src == "compact" else "ERC 活跃研究状态"
                lines.append(
                    "[%s] 项目：%s；当前阶段：%s %s（负责：%s）；退出条件缺口：%d 项；"
                    "恢复上下文请先运行 `python .claude/scripts/orchestrator.py next` 并读取 `Meta/decisions.md`。"
                    % (tag, st.get("project", ""), sid, stage["name"], stage["owner"], len(problems))
                )
        purpose = os.path.join(vault, "Meta", "purpose.md")
        if os.path.isfile(purpose):
            with open(purpose, encoding="utf-8-sig", errors="replace") as fh:
                if PURPOSE_PLACEHOLDER in fh.read():
                    lines.append("[ERC] Meta/purpose.md 仍为初始模板，尚未填写研究方向（须由研究者亲自填写，不得代编）。")
        if not lines:
            return
        out = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(lines),
            }
        }
        sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False) + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
