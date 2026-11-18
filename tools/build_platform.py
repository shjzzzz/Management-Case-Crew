#!/usr/bin/env python3
"""Generate Antigravity (agy) / Codex CLI files from the canonical Claude payload.

payload/.claude/ stays the single source. This script writes a staging tree that
the installer then copies into the vault without overwriting:

  stage/.agents/skills/<name>/...   (agy + Codex)  skills, script paths rewritten
  stage/.agents/scripts/...         (agy + Codex)  wiki_lint.py, orchestrator.py
  stage/.agents/pipeline-stages.json (agy + Codex)  stage definitions for orchestrator.py
  stage/.agents/agents/<name>.md    (agy + Codex)  agy subagent format; Codex reads them as role files
  stage/AGENTS.erc.md               (agy + Codex)  self-contained rules block for root AGENTS.md
  stage/.agents/hooks/*.py, routing-triggers.json, hooks.erc.json   (agy only)

Usage:
  build_platform.py build <payload_dir> <stage_dir> --platforms agy,codex
  build_platform.py merge-agents-md <vault_AGENTS.md> <block_file> [--update]
  build_platform.py update-maps <vault> [--check]  refresh folder + wikilink maps in CLAUDE.md/AGENTS.md
  build_platform.py sync-vault <vault> [--check]   refresh maps and regenerate AGENTS.md block from CLAUDE.md
  build_platform.py merge-agy-hooks <vault_hooks.json> <snippet.json>
"""
import json
import os
import re
import shutil
import sys

BEGIN = "<!-- ERC:BEGIN Economics Research Crew (generated; edit payload, not this block) -->"
END = "<!-- ERC:END -->"
MAP_FOLDER_BEGIN = "<!-- MAP:FOLDER:BEGIN (generated; do not edit manually) -->"
MAP_FOLDER_END = "<!-- MAP:FOLDER:END -->"
MAP_WIKILINK_BEGIN = "<!-- MAP:WIKILINK:BEGIN (generated; do not edit manually) -->"
MAP_WIKILINK_END = "<!-- MAP:WIKILINK:END -->"
MAP_BYTE_BUDGET = 3200
HOOK_KEY = "economics-research-crew"
AGENTS_MD_LIMIT = 24000  # agy truncates rule files above 24,000 bytes

MAP_SKIP_DIRS = {
    ".claude", ".agents", ".codex", ".obsidian", ".git",
    "_vendor", "node_modules", "__pycache__", "Templates",
}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FOLDER_PURPOSES = {
    "00-Inbox": "待整理资料",
    "01-Research-Projects": "案例研究项目",
    "03-Literature": "文献与案例笔记",
    "03-Literature/_sources": "原始来源（只读）",
    "04-Theories": "管理学理论框架",
    "05-Methods": "案例与测算方法",
    "06-Data": "数据目录",
    "06-Data/raw": "原始数据（只读）",
    "06-Data/processed": "衍生数据与测算表",
    "06-Data/metadata": "数据字典",
    "07-Code": "测算与编码脚本",
    "07-Code/python": "Python 脚本",
    "07-Code/R": "R 脚本",
    "07-Code/stata": "Stata 脚本",
    "08-Research-Notes": "案例分析笔记",
    "09-Writing": "论文与案例报告",
    "10-Archive": "已完成项目",
    "Meta": "目录/日志/规范",
    "MOC": "主题索引",
}

# Claude tool grants -> agy native tool names (from agy's built-in migrate-agent-settings skill;
# write_file / edit_file / read_file / run_command confirmed by a live PreToolUse probe)
TOOL_MAP = {
    "Read": ["read_file"], "Glob": ["read_file"], "Grep": ["read_file"],
    "Edit": ["edit_file"], "MultiEdit": ["edit_file"], "Write": ["write_file"],
    "Bash": ["run_command", "manage_task"], "WebSearch": ["search_web"], "WebFetch": ["search_web"],
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
- 本节由 Management Case Crew 安装器生成，与 Claude Code 的 `CLAUDE.md` 规则一致。
- Skills 位于 `.agents/skills/<名称>/SKILL.md`；文中的 `/名称`（如 `/literature-review`）指同名 Skill，按路由规则激活后照其步骤执行。
- Agent 说明位于 `.agents/agents/<名称>.md`。当前工具支持子 Agent 时按 Skill 要求派出；不支持时，读该文件并在主会话按其职责完成，独立审查须只依据产物并说明独立性降低。
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
    head = "---\nname: %s\ndescription: %s\nsubagent: true\nmainAgent: false\ntools: [%s]\n---\n" % (
        name, desc, ", ".join(tools))
    return head + rewrite(body, TEXT_REWRITES)


def build_rules_block(payload=None, claude_md=None, rules_md=None):
    """Rules block for AGENTS.md. Sources: the payload (install) or a vault's own
    CLAUDE.md + .claude/MANAGEMENT-CASE-RESEARCH.md (sync), so user edits propagate."""
    tpl = rd(claude_md or os.path.join(payload, "CLAUDE.template.md"))
    rules = rd(rules_md or os.path.join(payload, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))
    tpl = "\n".join(l for l in tpl.split("\n") if l.strip() != "@.claude/MANAGEMENT-CASE-RESEARCH.md").rstrip()
    body = rewrite(tpl, RULES_REWRITES) + "\n\n" + PLATFORM_NOTE + "\n" + rules.rstrip() + "\n"
    body = rewrite(body, TEXT_REWRITES)
    return BEGIN + "\n" + body + END + "\n"


def build(payload, stage, platforms):
    src = os.path.join(payload, ".claude")
    agents_root = os.path.join(stage, ".agents")
    # skills (shared by agy and Codex)
    sk_src = os.path.join(src, "skills")
    for name in sorted(os.listdir(sk_src)):
        d = os.path.join(sk_src, name)
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                s = os.path.join(root, f)
                t = os.path.join(agents_root, "skills", os.path.relpath(s, sk_src))
                if f.endswith(".md"):
                    wr(t, rewrite(rd(s), TEXT_REWRITES))
                else:
                    os.makedirs(os.path.dirname(t), exist_ok=True)
                    shutil.copyfile(s, t)
    # scripts
    sc_src = os.path.join(src, "scripts")
    if os.path.isdir(sc_src):
        for f in os.listdir(sc_src):
            if f.endswith(".py"):
                os.makedirs(os.path.join(agents_root, "scripts"), exist_ok=True)
                shutil.copyfile(os.path.join(sc_src, f), os.path.join(agents_root, "scripts", f))
    stages = os.path.join(src, "pipeline-stages.json")
    if os.path.exists(stages):
        shutil.copyfile(stages, os.path.join(agents_root, "pipeline-stages.json"))
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
            os.makedirs(os.path.join(agents_root, "hooks"), exist_ok=True)
            shutil.copyfile(os.path.join(src, "hooks", f), os.path.join(agents_root, "hooks", f))
        shutil.copyfile(os.path.join(src, "routing-triggers.json"), os.path.join(agents_root, "routing-triggers.json"))
        snippet = {HOOK_KEY: {
            "PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "python hooks/protect_raw.py", "timeout": 10}]}],
            "PreInvocation": [{"type": "command", "command": "python hooks/routing_hint.py", "timeout": 10}],
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
        return
    cur = rd(target)
    if BEGIN not in cur:
        wr(target, cur.rstrip() + "\n\n" + block)
        print("appended")
        return
    i, j = cur.index(BEGIN), cur.find(END)
    if j < 0:
        sys.exit("AGENTS.md has the ERC begin marker but no end marker; fix it by hand")
    old = cur[i:j + len(END)] + "\n"
    if old == block:
        print("unchanged")
    elif update:
        wr(target + ".new", cur[:i] + block + cur[j + len(END):].lstrip("\n"))
        print("pending")
    else:
        print("stale")


def _should_skip_dir(name):
    return name in MAP_SKIP_DIRS or name.startswith("_erc")


def _fit_lines_budget(header_lines, item_lines, footer_tmpl, budget):
    """Keep as many item_lines as fit within UTF-8 byte budget; append truncated notice if needed."""
    base = "\n".join(header_lines) + "\n"
    used = len(base.encode("utf-8"))
    kept = []
    for idx, line in enumerate(item_lines):
        cand = line + "\n"
        cand_len = len(cand.encode("utf-8"))
        remaining = len(item_lines) - idx - 1
        reserve = len((footer_tmpl % max(remaining, 1)).encode("utf-8")) + 1 if remaining > 0 else 0
        if used + cand_len + reserve <= budget:
            kept.append(line)
            used += cand_len
        else:
            omitted = len(item_lines) - idx
            kept.append(footer_tmpl % omitted)
            break
    return "\n".join(header_lines + kept)


def build_folder_map(vault, budget=1500):
    """Build a compact Folder Map of the vault (depth <= 2) within byte budget."""
    vault = os.path.abspath(vault)
    entries = []
    root_mds = sum(
        1 for f in os.listdir(vault)
        if os.path.isfile(os.path.join(vault, f))
        and f.lower().endswith(".md")
        and f not in ("CLAUDE.md", "CLAUDE.md.new", "AGENTS.md", "AGENTS.md.new", "AGENTS.md.bak")
    )

    def count_files(dirpath):
        md_cnt, other_cnt = 0, 0
        for r, dirs, files in os.walk(dirpath):
            dirs[:] = [d for d in sorted(dirs) if not _should_skip_dir(d)]
            for fn in files:
                if fn.lower().endswith(".md"):
                    md_cnt += 1
                else:
                    other_cnt += 1
        return md_cnt, other_cnt

    for d1 in sorted(os.listdir(vault)):
        p1 = os.path.join(vault, d1)
        if not os.path.isdir(p1) or _should_skip_dir(d1):
            continue
        md1, oth1 = count_files(p1)
        entries.append((1, d1, md1, oth1))
        for d2 in sorted(os.listdir(p1)):
            p2 = os.path.join(p1, d2)
            if not os.path.isdir(p2) or _should_skip_dir(d2):
                continue
            md2, oth2 = count_files(p2)
            entries.append((2, f"{d1}/{d2}", md2, oth2))

    header = [
        MAP_FOLDER_BEGIN,
        "### 文件夹地图（Folder Map）",
        f"> 自动扫描生成（根目录笔记 {root_mds} 篇，目录 {len(entries)} 个；排除 `.claude`/`.agents`/`.obsidian`/`Templates`）。",
    ]
    items = []
    for depth, rel, md_cnt, oth_cnt in entries:
        indent = "  " if depth == 2 else ""
        stat = f"{md_cnt} md" + (f", {oth_cnt} files" if oth_cnt else "")
        purpose = FOLDER_PURPOSES.get(rel, "")
        note = f" — {purpose}" if purpose else ""
        items.append(f"{indent}- `{rel}/` ({stat}){note}")

    footer_tmpl = "- ...（其余 %d 个子目录已按 24KB 预算省略，详见 `Meta/vault-map.md`）"
    # Reserve space for closing marker
    inner_budget = max(400, budget - len((MAP_FOLDER_END + "\n").encode("utf-8")))
    body = _fit_lines_budget(header, items, footer_tmpl, inner_budget)
    return body + "\n" + MAP_FOLDER_END + "\n"


def build_wikilink_map(vault, budget=1700):
    """Build a compact Obsidian [[wikilink]] map of the vault within byte budget."""
    vault = os.path.abspath(vault)
    pages = []  # (stem, rel_posix, full_path)
    stems = {}
    for r, dirs, files in os.walk(vault):
        dirs[:] = [d for d in sorted(dirs) if not _should_skip_dir(d)]
        for fn in sorted(files):
            if not fn.lower().endswith(".md"):
                continue
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, vault).replace("\\", "/")
            if rel in ("CLAUDE.md", "CLAUDE.md.new", "AGENTS.md", "AGENTS.md.new", "AGENTS.md.bak"):
                continue
            stem = os.path.splitext(fn)[0]
            pages.append((stem, rel, full))
            stems.setdefault(stem.lower(), []).append(stem)

    out_links = {}   # rel -> list of target stems (preserving order, unique)
    in_links = {}    # stem_lower -> set of source stems
    broken = []      # unique unresolved targets
    seen_broken = set()
    total_edges = 0

    for stem, rel, full in pages:
        try:
            text = rd(full)
        except OSError:
            continue
        targets = []
        seen_t = set()
        for m in WIKILINK_RE.finditer(text):
            raw_t = m.group(1).strip().replace("\\", "/").split("/")[-1]
            if raw_t.lower().endswith(".md"):
                raw_t = raw_t[:-3]
            if not raw_t or raw_t.lower() == stem.lower():
                continue
            key = raw_t.lower()
            if key in stems:
                canon = stems[key][0]
                if canon.lower() not in seen_t:
                    seen_t.add(canon.lower())
                    targets.append(canon)
                    in_links.setdefault(key, set()).add(stem)
                    total_edges += 1
            else:
                if key not in seen_broken:
                    seen_broken.add(key)
                    broken.append(raw_t)
        if targets:
            out_links[rel] = targets

    linked_items = []
    for stem, rel, _ in pages:
        outs = out_links.get(rel, [])
        ins = sorted(in_links.get(stem.lower(), set()))
        if not outs and not ins:
            continue
        deg = len(outs) + len(ins)
        out_str = ", ".join(f"[[{t}]]" for t in outs[:6]) + (f" (+{len(outs) - 6})" if len(outs) > 6 else "")
        in_str = ", ".join(f"[[{s}]]" for s in ins[:4]) + (f" (+{len(ins) - 4})" if len(ins) > 4 else "")
        arrow = f" → {out_str}" if out_str else f" ← {in_str}"
        linked_items.append((deg, len(ins), rel, f"- `[[{stem}]]` (`{rel}`, 入:{len(ins)}/出:{len(outs)}){arrow}"))

    linked_items.sort(key=lambda x: (-x[0], -x[1], x[2]))
    items = [x[3] for x in linked_items]
    if broken:
        b_str = ", ".join(f"`[[{b}]]`" for b in broken[:6]) + (f" (+{len(broken) - 6})" if len(broken) > 6 else "")
        items.append(f"- 待建/未解析双链 ({len(broken)}): {b_str}")
    if not items:
        items.append("> 暂无跨笔记 `[[双链]]`；使用 `[[页面名]]` 建立双链后运行 `Sync-AgentsMd.ps1` 自动更新。")

    header = [
        MAP_WIKILINK_BEGIN,
        "### 知识库双链地图（Obsidian Wikilink Map）",
        f"> 自动扫描生成；共 {len(pages)} 篇笔记，{total_edges} 条有效双链，{len(broken)} 个待建/未解析链接。检索优先从高连接 Hub 节点切入。",
    ]
    footer_tmpl = "- ...（其余 %d 条双链索引已按 24KB 预算省略，详见 `Meta/index.md`）"
    inner_budget = max(400, budget - len((MAP_WIKILINK_END + "\n").encode("utf-8")))
    body = _fit_lines_budget(header, items, footer_tmpl, inner_budget)
    return body + "\n" + MAP_WIKILINK_END + "\n"


def replace_marked_block(text, begin_marker, end_marker, new_block, insert_before=None):
    """Replace [begin_marker..end_marker] in text, or insert before insert_before / append."""
    if begin_marker in text and end_marker in text:
        i = text.index(begin_marker)
        j = text.index(end_marker, i) + len(end_marker)
        if j < len(text) and text[j] == "\n":
            j += 1
        return text[:i] + new_block + text[j:]
    if insert_before and insert_before in text:
        idx = text.index(insert_before)
        return text[:idx].rstrip() + "\n\n" + new_block + "\n" + text[idx:]
    return text.rstrip() + "\n\n" + new_block


def _apply_maps_to_text(text, folder_block, wikilink_block, insert_before=None):
    text = replace_marked_block(text, MAP_FOLDER_BEGIN, MAP_FOLDER_END, folder_block, insert_before=insert_before)
    text = replace_marked_block(text, MAP_WIKILINK_BEGIN, MAP_WIKILINK_END, wikilink_block, insert_before=insert_before)
    return text


def update_vault_maps(vault, check=False):
    """Refresh Folder Map and Obsidian Wikilink Map in CLAUDE.md (or AGENTS.md if no CLAUDE.md)."""
    folder_block = build_folder_map(vault, budget=1500)
    remaining = max(600, MAP_BYTE_BUDGET - len(folder_block.encode("utf-8")))
    wikilink_block = build_wikilink_map(vault, budget=remaining)

    claude_path = os.path.join(vault, "CLAUDE.md")
    agents_path = os.path.join(vault, "AGENTS.md")
    changed = False

    if os.path.exists(claude_path):
        cur = rd(claude_path)
        new = _apply_maps_to_text(cur, folder_block, wikilink_block, insert_before="@.claude/MANAGEMENT-CASE-RESEARCH.md")
        if new != cur:
            if check:
                return False
            wr(claude_path, new)
            changed = True
    elif os.path.exists(agents_path):
        cur = rd(agents_path)
        new = _apply_maps_to_text(cur, folder_block, wikilink_block, insert_before="## 平台说明（Antigravity / Codex）")
        if new != cur:
            if check:
                return False
            wr(agents_path, new)
            changed = True
    return True


def sync_vault(vault, check):
    """Refresh maps in CLAUDE.md, then regenerate the ERC block of <vault>/AGENTS.md from
    the vault's current CLAUDE.md and MANAGEMENT-CASE-RESEARCH.md. Only the marked block
    changes; the rest of AGENTS.md is untouched. --check only reports (exit 1 when out of sync)."""
    if not (os.path.exists(os.path.join(vault, "CLAUDE.md"))
            and os.path.exists(os.path.join(vault, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))):
        if os.path.exists(os.path.join(vault, "AGENTS.md")):
            ok = update_vault_maps(vault, check=check)
            if not ok and check:
                print("out-of-sync")
                sys.exit(1)
            print("in-sync" if check else "maps-updated")
            return
        print("skipped (no CLAUDE.md / .claude/MANAGEMENT-CASE-RESEARCH.md here, so nothing to sync from)")
        return
    maps_ok = update_vault_maps(vault, check=check)
    if check and not maps_ok:
        print("out-of-sync")
        sys.exit(1)
    block = build_rules_block(claude_md=os.path.join(vault, "CLAUDE.md"),
                              rules_md=os.path.join(vault, ".claude", "MANAGEMENT-CASE-RESEARCH.md"))
    size = len(block.encode("utf-8"))
    if size > AGENTS_MD_LIMIT:
        sys.exit("generated block is %d bytes, above agy's %d-byte limit; shorten CLAUDE.md" % (size, AGENTS_MD_LIMIT))
    target = os.path.join(vault, "AGENTS.md")
    cur = rd(target) if os.path.exists(target) else ""
    if BEGIN in cur:
        i, j = cur.index(BEGIN), cur.find(END)
        if j < 0:
            sys.exit("AGENTS.md has the ERC begin marker but no end marker; fix it by hand")
        if cur[i:j + len(END)] + chr(10) == block:
            print("in-sync")
            return
        new = cur[:i] + block + cur[j + len(END):].lstrip(chr(10))
    else:
        new = (cur.rstrip() + chr(10) * 2 if cur else "") + block
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
        build(argv[1], argv[2], plats)
    elif len(argv) >= 3 and argv[0] == "merge-agents-md":
        merge_agents_md(argv[1], argv[2], "--update" in argv)
    elif len(argv) >= 2 and argv[0] == "update-maps":
        ok = update_vault_maps(argv[1], check="--check" in argv)
        if not ok and "--check" in argv:
            print("maps out-of-sync")
            sys.exit(1)
        print("maps in-sync" if "--check" in argv else "maps updated")
    elif len(argv) >= 2 and argv[0] == "sync-vault":
        sync_vault(argv[1], "--check" in argv)
    elif len(argv) == 3 and argv[0] == "merge-agy-hooks":
        merge_agy_hooks(argv[1], argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
