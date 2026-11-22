#!/usr/bin/env python3
"""Generate Antigravity (agy) / Codex CLI files from the canonical Claude payload.

payload/.claude/ stays the single source. This script writes a staging tree that
the installer then copies into the vault without overwriting:

  stage/.agents/skills/<name>/...   (agy + Codex)  skills, script paths rewritten
  stage/.agents/scripts/...         (agy + Codex)  wiki_lint.py, orchestrator.py, paper_tools.py, refmgr.py
  stage/.agents/pipeline-stages.json (agy + Codex)  stage definitions for orchestrator.py
  stage/.agents/agents/<name>.md    (agy + Codex)  agy subagent format; Codex reads them as role files
  stage/AGENTS.erc.md               (agy + Codex)  self-contained rules block for root AGENTS.md
  stage/.agents/hooks/*.py, routing-triggers.json, hooks.erc.json   (agy only)

Usage:
  build_platform.py build <payload_dir> <stage_dir> --platforms agy,codex [--python-cmd CMD]
  build_platform.py merge-agents-md <vault_AGENTS.md> <block_file> [--update]
  build_platform.py sync-vault <vault> [--check]   regenerate AGENTS.md block from the vault's CLAUDE.md
  build_platform.py merge-agy-hooks <vault_hooks.json> <snippet.json>
"""
import json
import os
import re
import shutil
import sys

BEGIN = "<!-- ERC:BEGIN Economics Research Crew (generated; edit payload, not this block) -->"
END = "<!-- ERC:END -->"
HOOK_KEY = "economics-research-crew"
AGENTS_MD_LIMIT = 24000  # agy truncates rule files above 24,000 bytes

# Claude tool grants -> agy native tool names (from agy's built-in migrate-agent-settings skill;
# write_file / edit_file / read_file / run_command confirmed by a live PreToolUse probe)
TOOL_MAP = {
    "Read": ["read_file"], "Glob": ["read_file"], "Grep": ["read_file"],
    "Edit": ["edit_file"], "MultiEdit": ["edit_file"], "Write": ["write_file"],
    "Bash": ["run_command", "manage_task"], "PowerShell": ["run_command", "manage_task"],
    "WebSearch": ["search_web"], "WebFetch": ["search_web"],
}

TEXT_REWRITES = [
    (".claude/scripts/", ".agents/scripts/"),
]

RULES_REWRITES = [
    ("本目录同时是 Obsidian Vault 与 Claude Code 项目根目录。",
     "本目录同时是 Obsidian Vault 与 AI 编码助手（Claude Code / Antigravity / Codex）的项目根目录。"),
    ("**先用 Skill 工具调用该 Skill**", "**先调用（激活）该 Skill**"),
    ("Claude 的职责", "AI 助手的职责"),
    ("详细研究规则见下方 import 的 `.claude/MANAGEMENT-CASE-RESEARCH.md`", "详细研究规则见本文件后半部分"),
    ("不要在 `.claude`、`_vendor`", "不要在 `.claude`、`.agents`、`_vendor`"),
]

PLATFORM_NOTE = """## 平台说明（Antigravity / Codex）
- 本节由安装器生成，与 `CLAUDE.md` 规则一致。
- Skills 位于 `.agents/skills/<名称>/SKILL.md`；文中的 `/名称`（如 `/literature-review`）指同名 Skill，按路由规则激活后照其步骤执行。
- Agent 说明位于 `.agents/agents/<名称>.md`。工具支持子 Agent 时按 Skill 要求派出；不支持时，读该文件并在主会话按其职责完成，独立审查须只依据产物并说明独立性降低。
- 确定性脚本在 `.agents/scripts/`（如 `python .agents/scripts/wiki_lint.py lint --vault .`；项目编排用 `python .agents/scripts/orchestrator.py`）。
- 原始材料保护：Antigravity 由 `.agents/hooks.json` 的 hook 拦截；Codex 无此 hook，必须自觉遵守“`06-Data/raw` 与 `03-Literature/_sources` 只读”的规则。
"""


def rd(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig").replace("\r\n", "\n")


def wr(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def block_span(text):
    """(start, end) of the marked ERC block in text, which must contain BEGIN."""
    i, j = text.index(BEGIN), text.find(END)
    if j < 0:
        sys.exit("AGENTS.md has the ERC begin marker but no end marker; fix it by hand")
    return i, j + len(END)


def rewrite(text, pairs):
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def split_frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def fm_value(fm, key):
    m = re.search(r"^%s:\s*(.*)$" % re.escape(key), fm, re.M)
    return m.group(1).strip() if m else ""


def convert_agent(text, fallback_name):
    fm, body = split_frontmatter(text)
    fm = fm or ""
    name = fm_value(fm, "name").strip("\"'") or fallback_name
    desc = fm_value(fm, "description") or '"%s"' % name
    grants = [g.strip() for g in fm_value(fm, "tools").split(",") if g.strip()]
    if grants:
        tools = []
        for g in grants:
            for t in TOOL_MAP.get(g, []):
                if t not in tools:
                    tools.append(t)
    else:
        tools = ["read_file", "edit_file", "write_file", "run_command", "manage_task", "search_web"]
    extra = ""
    for k in ("data_access_level", "task_type"):
        v = fm_value(fm, k)
        if v:
            extra += "%s: %s\n" % (k, v)
    head = "---\nname: %s\ndescription: %s\nsubagent: true\nmainAgent: false\ntools: [%s]\n%s---\n" % (
        name, desc, ", ".join(tools), extra)
    return head + rewrite(body, TEXT_REWRITES)


def build_rules_block(payload=None, claude_md=None, rules_md=None):
    """Rules block for AGENTS.md. Sources: the payload (install) or a vault's own
    CLAUDE.md + .claude/MANAGEMENT-CASE-RESEARCH.md (sync), so user edits propagate."""
    tpl = rd(claude_md or os.path.join(payload, "CLAUDE.template.md"))
    rules = rd(rules_md or os.path.join(payload, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))
    tpl = "\n".join(l for l in tpl.split("\n") if l.strip() != "@.claude/MANAGEMENT-CASE-RESEARCH.md").rstrip()
    tpl = re.sub(r"(?m)^# .*Research Workspace[ \t]*$", "# Management Case Research Workspace", tpl, count=1)
    # Obsidian pads table cells for alignment; that padding is dead weight under agy's 24,000-byte cap
    def _compact(line):
        if not line.lstrip().startswith("|"):
            return line
        if re.fullmatch(r"[\s|:\-]+", line):
            return re.sub(r"-{3,}", "---", re.sub(r"[ \t]+", " ", line))
        return re.sub(r"(?<=\S)[ \t]{2,}(?=\|)", " ", line)
    tpl = "\n".join(_compact(l) for l in tpl.split("\n"))
    body = rewrite(tpl, RULES_REWRITES) + "\n\n" + PLATFORM_NOTE + "\n" + rules.rstrip() + "\n"
    body = rewrite(body, TEXT_REWRITES)
    return BEGIN + "\n" + body + END + "\n"


def default_python_cmd():
    if sys.platform == "win32":
        return "python"
    return "python3" if shutil.which("python3") else "python"


def build(payload, stage, platforms, python_cmd=None):
    python_cmd = python_cmd or default_python_cmd()
    src = os.path.join(payload, ".claude")
    agents_root = os.path.join(stage, ".agents")
    # skills (shared by agy and Codex)
    sk_src = os.path.join(src, "skills")
    for name in sorted(os.listdir(sk_src)):
        d = os.path.join(sk_src, name)
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in sorted(dirs) if x != "__pycache__"]
            for f in sorted(files):
                s = os.path.join(root, f)
                t = os.path.join(agents_root, "skills", os.path.relpath(s, sk_src))
                if f.endswith(".md"):
                    wr(t, rewrite(rd(s), TEXT_REWRITES))
                else:
                    copy(s, t)
    # scripts
    sc_src = os.path.join(src, "scripts")
    if os.path.isdir(sc_src):
        for f in os.listdir(sc_src):
            if f.endswith(".py"):
                copy(os.path.join(sc_src, f), os.path.join(agents_root, "scripts", f))
    stages = os.path.join(src, "pipeline-stages.json")
    if os.path.exists(stages):
        copy(stages, os.path.join(agents_root, "pipeline-stages.json"))
    # agents
    ag_src = os.path.join(src, "agents")
    for f in sorted(os.listdir(ag_src)):
        if f.endswith(".md"):
            wr(os.path.join(agents_root, "agents", f), convert_agent(rd(os.path.join(ag_src, f)), f[:-3]))
    # rules block
    block = build_rules_block(payload)
    size = len(block.encode("utf-8"))
    if size > AGENTS_MD_LIMIT:
        sys.exit("AGENTS block is %d bytes, above agy's %d-byte rule-file limit" % (size, AGENTS_MD_LIMIT))
    wr(os.path.join(stage, "AGENTS.erc.md"), block)
    # agy hooks
    if "agy" in platforms:
        for f in ("protect_raw.py", "routing_hint.py"):
            copy(os.path.join(src, "hooks", f), os.path.join(agents_root, "hooks", f))
        copy(os.path.join(src, "routing-triggers.json"), os.path.join(agents_root, "routing-triggers.json"))
        snippet = {HOOK_KEY: {
            "PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "%s hooks/protect_raw.py" % python_cmd, "timeout": 10}]}],
            "PreInvocation": [{"type": "command", "command": "%s hooks/routing_hint.py" % python_cmd, "timeout": 10}],
        }}
        wr(os.path.join(stage, "hooks.erc.json"), json.dumps(snippet, ensure_ascii=False, indent=2) + "\n")
    print("built %s (AGENTS block %d bytes)" % (",".join(sorted(platforms)), size))


def merge_agents_md(target, block_file, update):
    """Create AGENTS.md, or append the marked block; never overwrite user content.
    With --update and a stale block, write AGENTS.md.new (block replaced) for manual merge."""
    block = rd(block_file)
    if not os.path.exists(target):
        wr(target, block)
        print("created")
        return "created"
    cur = rd(target)
    if BEGIN not in cur:
        wr(target, cur.rstrip() + "\n\n" + block)
        print("appended")
        return "appended"
    i, end = block_span(cur)
    if cur[i:end] + "\n" == block:
        print("unchanged")
        return "unchanged"
    elif update:
        wr(target + ".new", cur[:i] + block + cur[end:].lstrip("\n"))
        print("pending")
        return "pending"
    else:
        print("stale")
        return "stale"


def sync_vault(vault, check):
    """Regenerate the ERC block of <vault>/AGENTS.md from the vault's current CLAUDE.md and
    MANAGEMENT-CASE-RESEARCH.md. Only the marked block changes; the rest of AGENTS.md is untouched.
    --check only reports (exit 1 when out of sync)."""
    if not (os.path.exists(os.path.join(vault, "CLAUDE.md"))
            and os.path.exists(os.path.join(vault, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))):
        print("skipped (no CLAUDE.md / .claude/MANAGEMENT-CASE-RESEARCH.md here, so nothing to sync from)")
        return
    block = build_rules_block(claude_md=os.path.join(vault, "CLAUDE.md"),
                              rules_md=os.path.join(vault, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))
    target = os.path.join(vault, "AGENTS.md")
    cur = rd(target) if os.path.exists(target) else ""
    if BEGIN in cur:
        i, end = block_span(cur)
        if cur[i:end] + "\n" == block:
            print("in-sync")
            return
        new = cur[:i] + block + cur[end:].lstrip("\n")
    else:
        new = (cur.rstrip() + "\n\n" if cur else "") + block
    size = len(new.encode("utf-8"))
    if size > AGENTS_MD_LIMIT:
        sys.exit("resulting AGENTS.md would be %d bytes, above agy's %d-byte limit; shorten CLAUDE.md or custom AGENTS.md rules" % (size, AGENTS_MD_LIMIT))
    if check:
        print("out-of-sync")
        sys.exit(1)
    if cur:
        shutil.copyfile(target, target + ".bak")
    wr(target, new)
    print("synced (previous AGENTS.md saved as AGENTS.md.bak)" if cur else "created")


def merge_agy_hooks(target, snippet_file):
    """Set our named hook key in .agents/hooks.json; leave every other key untouched."""
    snippet = json.loads(rd(snippet_file))
    data = {}
    if os.path.exists(target):
        data = json.loads(rd(target))
        if not isinstance(data, dict):
            sys.exit("hooks.json is not a JSON object; not modified")
    data.update(snippet)
    tmp = target + ".tmp"
    wr(tmp, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, target)
    print("merged")


def main(argv):
    if len(argv) >= 3 and argv[0] == "build":
        plats = {"agy", "codex"}
        if "--platforms" in argv:
            plats = set(argv[argv.index("--platforms") + 1].split(","))
        py_cmd = argv[argv.index("--python-cmd") + 1] if "--python-cmd" in argv else None
        build(argv[1], argv[2], plats, py_cmd)
    elif len(argv) >= 3 and argv[0] == "merge-agents-md":
        merge_agents_md(argv[1], argv[2], "--update" in argv)
    elif len(argv) >= 2 and argv[0] == "sync-vault":
        sync_vault(argv[1], "--check" in argv)
    elif len(argv) == 3 and argv[0] == "merge-agy-hooks":
        merge_agy_hooks(argv[1], argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
