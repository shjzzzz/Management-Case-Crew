#!/usr/bin/env python3
"""Orchestration layer for the Research Director (/research-pipeline).

Keeps a machine-readable project state (STATE.json), an append-only run ledger
(Meta/run-ledger.jsonl) and enforces stage order / retries / researcher gates.
Pure standard library; no model calls.

Commands (run from the vault root, or pass --vault):
  init <project_dir> [--title T]     create STATE.json at S1 (project_dir under 01-Research-Projects/)
  status [--json]                    where the project is
  next                               what to do now (stage, owner, missing artifacts, retries)
  artifact <path>... [--stage Sn]    register stage outputs (must exist, be non-empty, be inside the vault)
  verify [--stage Sn]                check the stage's exit criteria (exit 1 when not met)
  gate --decision pass|revise|return|stop --note TEXT [--to Sn] [--force] [--fatal-resolved]
                                     record the researcher's decision at a gate (only the researcher decides)
  fail --agent A --reason R          record a failed dispatch; reports retry budget
  recover                            mark stale "running" dispatches abandoned
  enforce on|off                     toggle hook enforcement for this project
  log [-n N]                         tail the run ledger
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES_FILE = os.path.join(os.path.dirname(HERE), "pipeline-stages.json")  # .claude/ or .agents/ next to scripts/
PROJECTS_DIR = "01-Research-Projects"
LEDGER = os.path.join("Meta", "run-ledger.jsonl")


# ---------------------------------------------------------------- basics
def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load_cfg():
    with open(STAGES_FILE, encoding="utf-8-sig") as fh:
        return json.load(fh)


def find_vault(start=None):
    d = os.path.abspath(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, "Meta")) and os.path.isdir(os.path.join(d, PROJECTS_DIR)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def rjson(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def wjson(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def ledger_append(vault, event, **fields):
    rec = {"ts": now(), "event": event}
    rec.update({k: v for k, v in fields.items() if v is not None})
    try:
        with open(os.path.join(vault, LEDGER), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass  # observability must never break the research flow


def ledger_read(vault):
    path = os.path.join(vault, LEDGER)
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def state_paths(vault):
    return sorted(glob.glob(os.path.join(vault, PROJECTS_DIR, "*", "STATE.json")))


def active_project(vault):
    """Most recently updated STATE.json whose status is active, or None."""
    best = None
    for p in state_paths(vault):
        try:
            st = rjson(p)
        except (OSError, ValueError):
            continue
        if st.get("active"):
            if best is None or st.get("updated", "") > best[1].get("updated", ""):
                best = (p, st)
    return best


def stage_index(cfg, sid):
    for i, s in enumerate(cfg["stages"]):
        if s["id"] == sid:
            return i
    return -1


def agent_stage_index(cfg, agent):
    for i, s in enumerate(cfg["stages"]):
        if agent in s.get("agents", []):
            return i
    return -1


def running_dispatches(vault, cfg):
    """Dispatches that were requested/started but have no stop yet and are not stale or abandoned."""
    stale = datetime.timedelta(minutes=cfg.get("stale_minutes", 30))
    t_now = datetime.datetime.now().astimezone()
    open_ = {}
    for r in ledger_read(vault):
        ev, key = r.get("event"), r.get("agent_id") or r.get("req_id")
        try:
            ts = datetime.datetime.fromisoformat(r["ts"])
        except (KeyError, ValueError):
            continue
        if ev == "recover":
            open_.clear()
        elif ev == "dispatch_request":
            open_[r["req_id"]] = (ts, r.get("agent"), "req")
        elif ev == "start":
            # a start consumes the oldest pending request for the same agent
            for k, (t0, a, kind) in list(open_.items()):
                if kind == "req" and a == r.get("agent"):
                    del open_[k]
                    break
            open_[key] = (ts, r.get("agent"), "run")
        elif ev == "stop":
            open_.pop(key, None)
    # A request normally becomes a start within seconds; one that never starts (permission denied,
    # tool error) must not hold a slot for the whole stale window.
    pending = datetime.timedelta(minutes=2)
    return [(k, v) for k, v in open_.items() if t_now - v[0] < (pending if v[2] == "req" else stale)]


def inside(path, root):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:  # different drives
        return False


def project_ctx(args, need=True, readonly=False):
    vault = find_vault(getattr(args, "vault", None))
    if not vault:
        sys.exit("找不到研究库根目录（需要同时有 Meta/ 和 %s/）；请在库根目录运行或加 --vault。" % PROJECTS_DIR)
    proj = getattr(args, "project", None)
    if proj:
        p = os.path.join(vault, PROJECTS_DIR, proj, "STATE.json") if not os.path.isabs(proj) else os.path.join(proj, "STATE.json")
        if not os.path.exists(p):
            sys.exit("没有找到 %s" % p)
        return vault, p, rjson(p)
    ap = active_project(vault)
    if not ap and readonly:  # stopped/completed projects can still be inspected
        newest = None
        for p in state_paths(vault):
            try:
                st = rjson(p)
            except (OSError, ValueError):
                continue
            if newest is None or st.get("updated", "") > newest[1].get("updated", ""):
                newest = (p, st)
        ap = newest
    if not ap:
        if need:
            sys.exit("没有进行中的项目。先运行：orchestrator.py init 01-Research-Projects/<项目名>")
        return vault, None, None
    return vault, ap[0], ap[1]


def save(vault, path, st):
    st["updated"] = now()
    wjson(path, st)


# ---------------------------------------------------------------- verify
def verify_stage(vault, cfg, st, sid):
    s = cfg["stages"][stage_index(cfg, sid)]
    rec = st["stages"][sid]
    problems, texts = [], []
    arts = rec.get("artifacts", [])
    for a in arts:
        p = os.path.join(vault, a)
        if not os.path.isfile(p):
            problems.append("产物不存在：%s" % a)
        elif os.path.getsize(p) == 0:
            problems.append("产物为空：%s" % a)
        else:
            try:
                with open(p, encoding="utf-8-sig", errors="replace") as fh:
                    texts.append(fh.read(2_000_000))
            except OSError:
                pass
    if len(arts) < s.get("min_artifacts", 0):
        problems.append("已登记产物 %d 个，至少需要 %d 个" % (len(arts), s.get("min_artifacts", 0)))
    for pat in s.get("require_name", []):
        if not any(re.search(pat, a, re.I) for a in arts):
            problems.append("没有路径匹配 /%s/ 的产物" % pat)
    blob = "\n".join(texts)
    for pat in s.get("require_text", []):
        if not re.search(pat, blob, re.I):
            problems.append("产物中找不到必需内容：%s" % pat)
    checks = s.get("checks", [])
    if checks:
        files = [os.path.join(vault, a) for a in arts if os.path.isfile(os.path.join(vault, a))]
        try:
            import paper_tools  # same folder; imported lazily (it imports this module)
        except ImportError:
            problems.append("缺少 paper_tools.py，无法执行检查项：%s" % ", ".join(checks))
        else:
            for chk in checks:
                problems += paper_tools.stage_check(vault, chk, files)
    return problems


# ---------------------------------------------------------------- commands
def cmd_init(a):
    cfg = load_cfg()
    vault = find_vault(a.vault)
    if not vault:
        sys.exit("找不到研究库根目录（需要同时有 Meta/ 和 %s/）。" % PROJECTS_DIR)
    pdir = a.project_dir if os.path.isabs(a.project_dir) else os.path.join(vault, a.project_dir)
    pdir = os.path.abspath(pdir)
    if os.path.commonpath([pdir, os.path.join(vault, PROJECTS_DIR)]) != os.path.join(vault, PROJECTS_DIR) or \
            os.path.dirname(pdir) != os.path.join(vault, PROJECTS_DIR):
        sys.exit("项目目录必须是 %s/<项目名>。" % PROJECTS_DIR)
    sp = os.path.join(pdir, "STATE.json")
    if os.path.exists(sp):
        sys.exit("已存在 %s；用 status 查看，不重复初始化。" % sp)
    os.makedirs(pdir, exist_ok=True)
    name = os.path.basename(pdir)
    st = {"project": name, "title": a.title or name, "active": True, "enforce": True, "status": "active",
          "created": now(), "stage": cfg["stages"][0]["id"],
          "stages": {s["id"]: {"status": "pending", "artifacts": [], "attempts": {}} for s in cfg["stages"]},
          "history": []}
    st["stages"][st["stage"]]["status"] = "in_progress"
    save(vault, sp, st)
    ledger_append(vault, "init", project=name, stage=st["stage"])
    print("已创建 %s（阶段 %s）。" % (os.path.relpath(sp, vault), st["stage"]))


def cmd_status(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a, readonly=True)
    if a.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return
    print("项目：%s  状态：%s  当前阶段：%s  强制：%s" % (st["project"], st["status"], st["stage"], "开" if st.get("enforce", True) else "关"))
    for s in cfg["stages"]:
        r = st["stages"][s["id"]]
        mark = {"passed": "✔", "in_progress": "▶", "pending": "·"}.get(r["status"], "?")
        print(" %s %s %-6s %-12s 产物 %d" % (mark, s["id"], s["name"], r["status"], len(r["artifacts"])))
    run = running_dispatches(vault, cfg)
    if run:
        print("运行中/待启动的派出：%d（%s）" % (len(run), ", ".join(str(v[1]) for _, v in run)))


def cmd_next(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a, readonly=True)
    if st["status"] != "active":
        print("项目已 %s，没有下一步。" % st["status"])
        return
    sid = st["stage"]
    s = cfg["stages"][stage_index(cfg, sid)]
    rec = st["stages"][sid]
    print("当前阶段 %s %s；负责：%s" % (sid, s["name"], s["owner"]))
    if s.get("agents"):
        budget = 1 + cfg.get("max_retries", 2)
        for ag in s["agents"]:
            n = rec["attempts"].get(ag, 0)
            print("  Agent %s：已失败 %d 次，%s" % (ag, n, "可重试" if n < budget else "已达重试上限，停下并向研究者报告"))
    problems = verify_stage(vault, cfg, st, sid)
    if problems:
        print("通过关卡前还缺：")
        for p in problems:
            print("  - " + p)
    else:
        print("退出条件已满足。请向研究者汇报，并询问关卡问题：「%s」" % s["gate"])
        print("研究者表态后，再运行：orchestrator.py gate --decision pass|revise|return|stop --note \"…\"")


def cmd_artifact(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a)
    sid = a.stage or st["stage"]
    if sid not in st["stages"]:
        sys.exit("未知阶段 %s" % sid)
    added = []
    for raw in a.paths:
        p = os.path.abspath(raw if os.path.isabs(raw) else os.path.join(vault, raw))
        if not inside(p, vault):
            sys.exit("产物必须在研究库内：%s" % raw)
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            sys.exit("产物不存在或为空：%s" % raw)
        rel = os.path.relpath(p, vault).replace("\\", "/")
        if rel not in st["stages"][sid]["artifacts"]:
            st["stages"][sid]["artifacts"].append(rel)
            added.append(rel)
    save(vault, path, st)
    ledger_append(vault, "artifact", project=st["project"], stage=sid, artifacts=added)
    print("已登记 %d 个产物到 %s。" % (len(added), sid))


def cmd_verify(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a)
    sid = a.stage or st["stage"]
    problems = verify_stage(vault, cfg, st, sid)
    ledger_append(vault, "verify", project=st["project"], stage=sid, ok=not problems, problems=problems or None)
    if problems:
        print("阶段 %s 未满足退出条件：" % sid)
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("阶段 %s 的退出条件已满足。" % sid)


def cmd_gate(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a)
    if st["status"] != "active":
        sys.exit("项目已 %s。" % st["status"])
    if not (a.note or "").strip():
        sys.exit("必须用 --note 写明研究者的决定与理由。")
    sid = st["stage"]
    idx = stage_index(cfg, sid)
    rec = st["stages"][sid]
    entry = {"ts": now(), "stage": sid, "decision": a.decision, "note": a.note, "forced": bool(a.force)}
    if a.decision == "pass":
        problems = verify_stage(vault, cfg, st, sid)
        if sid == "S7" and not a.fatal_resolved:
            problems.append("S7 通过必须加 --fatal-resolved，表示研究者确认致命问题已解决")
        if problems and not a.force:
            print("阶段 %s 未满足退出条件，不能通过（研究者坚持时用 --force 并在 --note 写明原因）：" % sid)
            for p in problems:
                print("  - " + p)
            sys.exit(1)
        rec["status"] = "passed"
        if idx + 1 < len(cfg["stages"]):
            nxt = cfg["stages"][idx + 1]["id"]
            st["stage"] = nxt
            st["stages"][nxt]["status"] = "in_progress"
            msg = "阶段 %s 已通过，进入 %s %s。" % (sid, nxt, cfg["stages"][idx + 1]["name"])
        else:
            st["status"], st["active"] = "completed", False
            msg = "全部阶段通过，项目完成。"
    elif a.decision == "revise":
        rec["attempts"] = {}
        rec["status"] = "in_progress"
        msg = "阶段 %s 退回修改（重试计数已清零）。" % sid
    elif a.decision == "return":
        if not a.to or a.to not in st["stages"] or stage_index(cfg, a.to) > idx:
            sys.exit("--to 必须是当前阶段或更早的阶段（如 S4）。")
        for s in cfg["stages"][stage_index(cfg, a.to):]:
            st["stages"][s["id"]]["status"] = "pending"
            st["stages"][s["id"]]["attempts"] = {}
        st["stage"] = a.to
        st["stages"][a.to]["status"] = "in_progress"
        entry["to"] = a.to
        msg = "已从 %s 退回到 %s；其后阶段需重新通过关卡。" % (sid, a.to)
    else:  # stop
        st["status"], st["active"] = "stopped", False
        msg = "项目已停止。"
    st["history"].append(entry)
    save(vault, path, st)
    ledger_append(vault, "gate", project=st["project"], stage=sid, decision=a.decision, note=a.note,
                  to=entry.get("to"), forced=bool(a.force) or None)
    print(msg)


def cmd_fail(a):
    cfg = load_cfg()
    vault, path, st = project_ctx(a)
    sid = st["stage"]
    rec = st["stages"][sid]
    rec["attempts"][a.agent] = rec["attempts"].get(a.agent, 0) + 1
    n, budget = rec["attempts"][a.agent], 1 + cfg.get("max_retries", 2)
    save(vault, path, st)
    ledger_append(vault, "fail", project=st["project"], stage=sid, agent=a.agent, reason=a.reason, attempts=n)
    if n < budget:
        print("已记录失败（%s 第 %d 次）。还可重试 %d 次；请先说明原因再重试。" % (a.agent, n, budget - n))
    else:
        print("%s 已失败 %d 次，达到上限。停下，向研究者报告原因；研究者决定 revise 后计数才清零。" % (a.agent, n))


def cmd_recover(a):
    vault = find_vault(a.vault)
    if not vault:
        sys.exit("找不到研究库根目录。")
    cfg = load_cfg()
    n = len(running_dispatches(vault, cfg))
    ledger_append(vault, "recover", abandoned=n)
    print("已把 %d 个残留的运行中派出标记为 abandoned。" % n)


def cmd_enforce(a):
    vault, path, st = project_ctx(a)
    st["enforce"] = a.mode == "on"
    save(vault, path, st)
    ledger_append(vault, "enforce", project=st["project"], enforce=st["enforce"])
    print("强制已%s。" % ("开启" if st["enforce"] else "关闭（hook 只记录，不拦截）"))


def cmd_log(a):
    vault = find_vault(a.vault)
    if not vault:
        sys.exit("找不到研究库根目录。")
    for r in ledger_read(vault)[-a.n:]:
        print(json.dumps(r, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--project", help="项目目录名（默认：进行中的项目）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("project_dir"); p.add_argument("--title"); p.set_defaults(f=cmd_init)
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_status)
    p = sub.add_parser("next"); p.set_defaults(f=cmd_next)
    p = sub.add_parser("artifact"); p.add_argument("paths", nargs="+"); p.add_argument("--stage"); p.set_defaults(f=cmd_artifact)
    p = sub.add_parser("verify"); p.add_argument("--stage"); p.set_defaults(f=cmd_verify)
    p = sub.add_parser("gate")
    p.add_argument("--decision", required=True, choices=["pass", "revise", "return", "stop"])
    p.add_argument("--note", default="")
    p.add_argument("--to")
    p.add_argument("--force", action="store_true")
    p.add_argument("--fatal-resolved", action="store_true")
    p.set_defaults(f=cmd_gate)
    p = sub.add_parser("fail"); p.add_argument("--agent", required=True); p.add_argument("--reason", required=True); p.set_defaults(f=cmd_fail)
    p = sub.add_parser("recover"); p.set_defaults(f=cmd_recover)
    p = sub.add_parser("enforce"); p.add_argument("mode", choices=["on", "off"]); p.set_defaults(f=cmd_enforce)
    p = sub.add_parser("log"); p.add_argument("-n", type=int, default=20); p.set_defaults(f=cmd_log)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    main()
