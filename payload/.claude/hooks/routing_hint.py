#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministic routing hint.

Matches the user's prompt against .claude/routing-triggers.json and, when an
intent matches, prints a one-paragraph hint that Claude Code adds to the
context ("this request maps to /skill; invoke it first"). It never blocks.

- Prompts that already start with "/" (explicit command) get no hint.
- No match -> no output (conceptual questions are answered directly).
- Fails open (exit 0, no output) on any error.

Also runs as an Antigravity (agy) PreInvocation hook: input has
`hookEventName: PreInvocation` and `lastUserInput`; the hint is injected as a
system message only on the first model call of a turn (`invocationNum == 0`),
and the output is always JSON (`{}` when there is nothing to add).
"""
import json
import os
import re
import sys


def load_routes():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(os.path.dirname(here), "routing-triggers.json")
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh).get("routes", [])


def match(prompt, routes):
    hits = []
    for r in routes:
        for pat in r.get("patterns", []):
            m = re.search(pat, prompt, re.IGNORECASE)
            if m:
                hits.append((r["skill"], m.group(0)))
                break
    return hits


def hint(prompt):
    if not prompt or prompt.startswith("/"):
        return ""
    hits = match(prompt, load_routes())
    if not hits:
        return ""
    primary, trigger = hits[0]
    others = [h[0] for h in hits[1:]]
    msg = ("[routing] 本请求匹配项目 Skill `/%s`（触发词：%s）。按项目路由规则：先调用（激活）Skill `%s`，"
           "再按它的步骤执行；不要在主会话里自行完成该流程。" % (primary, trigger, primary))
    if others:
        msg += "该 Skill 执行中可能还涉及：%s（按需在流程内调用，不要同时启动）。" % "、".join("/" + o for o in others)
    msg += "若请求其实只是概念性短问题，可直接回答。"
    return msg


def main():
    raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")  # hosts send UTF-8; Windows python would decode as GBK
    agy = '"PreInvocation"' in raw
    try:
        data = json.loads(raw)
        if data.get("hookEventName") == "PreInvocation":  # Antigravity
            msg = hint((data.get("lastUserInput") or "").strip()) if data.get("invocationNum", 0) == 0 else ""
            out = {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]} if msg else {}
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            return 0
        msg = hint((data.get("prompt") or "").strip())
    except Exception:
        if agy:
            sys.stdout.write("{}\n")  # agy expects JSON even when we have nothing to add
        return 0
    if msg:
        sys.stdout.write(msg + "\n")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
