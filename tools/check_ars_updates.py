#!/usr/bin/env python3
"""Adaptive upstream update tracker for Imbad0202/academic-research-skills (ARS).

Pure standard library, zero LLM quota. Fetches ARS releases and commits since the
last audited baseline in payload/Meta/upstream-ars.json, classifies relevant changes
onto Economics Research Crew (ERC) modules, filters explicitly excluded areas, and
emits a structured native-adoption brief (never copies CC-BY-NC code).

Usage:
  python tools/check_ars_updates.py check [--manifest PATH] [--mock JSON] [--out FILE] [--json]
  python tools/check_ars_updates.py mark-audited --tag TAG --sha SHA [--manifest PATH] [--note TEXT]

Exit codes:
  0  up to date (or mark-audited succeeded)
  2  upstream updates found (adoption brief emitted)
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MANIFEST = os.path.join(ROOT, "payload", "Meta", "upstream-ars.json")


def load_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def gh_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "EconomicsResearchCrew-UpstreamTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_upstream(repo, mock_path=None):
    if mock_path:
        data = load_json(mock_path)
        return data.get("releases", []), data.get("commits", [])
    base = "https://api.github.com/repos/" + repo
    try:
        rels = gh_get(base + "/releases?per_page=10")
        commits = gh_get(base + "/commits?per_page=25")
    except Exception as exc:
        sys.exit("无法获取上游 %s 更新（可检查网络或使用 --mock）：%s" % (repo, exc))
    norm_rels = [{"tag": r.get("tag_name", ""), "published_at": r.get("published_at", ""),
                  "name": r.get("name", ""), "body": r.get("body", "")} for r in rels]
    norm_commits = [{"sha": c.get("sha", ""), "date": ((c.get("commit") or {}).get("committer") or {}).get("date", "")[:10],
                     "message": ((c.get("commit") or {}).get("message") or "").splitlines()[0]} for c in commits]
    return norm_rels, norm_commits


def new_since(items, key, stop_val, prefix=False):
    out = []
    for it in items:
        v = str(it.get(key, ""))
        if stop_val and (v.startswith(stop_val) if prefix else v == stop_val):
            break
        out.append(it)
    return out


def classify_text(text, manifest):
    low = (text or "").lower()
    caps, files = [], []
    for cap in manifest.get("capability_map", []):
        if any(k.lower() in low for k in cap.get("keywords", [])):
            caps.append(cap["id"])
            for f in cap.get("erc_files", []):
                if f not in files:
                    files.append(f)
    if caps:
        return "relevant", caps, files
    for ex in manifest.get("explicitly_excluded", []):
        if any(k.lower() in low for k in ex.get("keywords", [])):
            return "excluded", [ex["id"]], []
    return "unclassified", [], []


def render_markdown(manifest, latest_tag, latest_sha, new_rels, new_commits, mapped):
    L = [
        "# ARS 上游更新自适应适配简报",
        "",
        "- 上游仓库：`%s`（%s；**仅借鉴设计模式，原生重写，严禁拷贝 CC-BY-NC 代码**）" % (manifest["repo"], manifest["license"]),
        "- 已审计基线：`%s`（`%s`，%s）" % (manifest["last_audited_tag"], manifest["last_audited_sha"], manifest["last_audited_date"]),
        "- 上游最新：`%s`（`%s`）" % (latest_tag or "unknown", (latest_sha or "")[:8]),
        "- 新增发布：%d 个；新增提交：%d 条" % (len(new_rels), len(new_commits)),
        "",
    ]
    if new_rels:
        L.append("## 1. 新增 Release 摘要")
        for r in new_rels:
            L.append("- **%s**（%s）：%s" % (r["tag"], (r.get("published_at") or "")[:10], r.get("name") or ""))
        L.append("")
    rel_items = [m for m in mapped if m["bucket"] == "relevant"]
    exc_items = [m for m in mapped if m["bucket"] == "excluded"]
    oth_items = [m for m in mapped if m["bucket"] == "unclassified"]
    L.append("## 2. 高相关变更 → 受影响的 ERC 模块（建议人工/AI 审阅并原生重构）")
    if rel_items:
        for it in rel_items:
            L.append("- [%s] `%s` → 模块：%s" % (it["kind"], it["summary"], ", ".join(it["caps"])))
            L.append("  - 建议核查 ERC 文件：%s" % "、".join("`%s`" % f for f in it["files"]))
    else:
        L.append("- 无直接命中核心能力映射表的变更。")
    L += ["", "## 3. 自动过滤的排除项（不适用 ERC 定位）"]
    L += (["- `%s`（命中排除规则：%s）" % (it["summary"], ", ".join(it["caps"])) for it in exc_items] or ["- 无"])
    L += ["", "## 4. 未归类提交（快速扫读）"]
    L += (["- `%s`" % it["summary"] for it in oth_items[:15]] or ["- 无"])
    L += [
        "",
        "## 5. 完成适配后的推进命令",
        "```powershell",
        "python tools/check_ars_updates.py mark-audited --tag %s --sha %s" % (latest_tag or manifest["last_audited_tag"], (latest_sha or manifest["last_audited_sha"])[:8]),
        "```",
        "",
    ]
    return "\n".join(L)


def cmd_check(a):
    m = load_json(a.manifest)
    rels, commits = fetch_upstream(m["repo"], a.mock)
    latest_tag = rels[0]["tag"] if rels else m["last_audited_tag"]
    latest_sha = commits[0]["sha"] if commits else m["last_audited_sha"]
    new_rels = new_since(rels, "tag", m["last_audited_tag"], prefix=False)
    new_commits = new_since(commits, "sha", m["last_audited_sha"], prefix=True)
    has_updates = bool(new_rels or new_commits)
    mapped = []
    for r in new_rels:
        b, caps, files = classify_text((r.get("name") or "") + " " + (r.get("body") or ""), m)
        mapped.append({"kind": "release", "summary": "%s: %s" % (r["tag"], (r.get("name") or "")[:90]),
                       "bucket": b, "caps": caps, "files": files})
    for c in new_commits:
        b, caps, files = classify_text(c.get("message", ""), m)
        mapped.append({"kind": "commit", "summary": "%s %s" % (c["sha"][:8], c.get("message", "")[:90]),
                       "bucket": b, "caps": caps, "files": files})
    result = {
        "up_to_date": not has_updates,
        "baseline_tag": m["last_audited_tag"], "baseline_sha": m["last_audited_sha"],
        "latest_tag": latest_tag, "latest_sha": latest_sha[:8],
        "new_releases": len(new_rels), "new_commits": len(new_commits),
        "relevant_count": sum(1 for x in mapped if x["bucket"] == "relevant"),
        "items": mapped,
    }
    if not has_updates:
        if a.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("已是最新：ARS 基线 %s (%s) 与上游一致，无新增发布或提交。" % (m["last_audited_tag"], m["last_audited_sha"][:8]))
        return 0
    md = render_markdown(m, latest_tag, latest_sha, new_rels, new_commits, mapped)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(md)
    return 2


def cmd_mark(a):
    m = load_json(a.manifest)
    m["last_audited_tag"] = a.tag.strip()
    m["last_audited_sha"] = a.sha.strip()
    m["last_audited_date"] = datetime.date.today().isoformat()
    if a.note:
        m["last_audit_note"] = a.note.strip()
    save_json(a.manifest, m)
    print("已更新 ARS 审计基线：%s (%s, %s)" % (m["last_audited_tag"], m["last_audited_sha"], m["last_audited_date"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("check")
    pc.add_argument("--manifest", default=DEFAULT_MANIFEST)
    pc.add_argument("--mock", help="Offline JSON fixture with {releases:[], commits:[]}")
    pc.add_argument("--out", help="Write Markdown adoption brief to path")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(f=cmd_check)
    pm = sub.add_parser("mark-audited")
    pm.add_argument("--tag", required=True)
    pm.add_argument("--sha", required=True)
    pm.add_argument("--manifest", default=DEFAULT_MANIFEST)
    pm.add_argument("--note")
    pm.set_defaults(f=cmd_mark)
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    sys.exit(main())
