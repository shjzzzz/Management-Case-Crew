#!/usr/bin/env python3
"""Merge the Crew hook snippet into a Claude Code settings.json, idempotently.

Usage: python merge_hooks.py SETTINGS_JSON SNIPPET_JSON

- Creates SETTINGS_JSON if missing.
- Refuses (exit 1, file untouched) if SETTINGS_JSON is not valid JSON.
- A hook is considered present if some command in the same event already
  references the same script file name; present hooks are never duplicated,
  but their matcher is widened when the snippet covers more tools (upgrades).
- Preserves every other key. Writes only when something changed.
"""
import json
import os
import re
import sys


def script_names(group):
    names = set()
    for h in group.get("hooks", []):
        m = re.search(r"([\w.-]+\.py)", h.get("command", ""))
        if m:
            names.add(m.group(1))
    return names


def main(settings_path, snippet_path):
    with open(snippet_path, encoding="utf-8-sig") as fh:
        snippet = json.load(fh)
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8-sig") as fh:
                settings = json.load(fh)
        except ValueError as e:
            sys.stderr.write("settings.json is not valid JSON, left untouched: %s\n" % e)
            return 1
        if not isinstance(settings, dict):
            sys.stderr.write("settings.json top level is not an object, left untouched\n")
            return 1
    else:
        settings = {}
    changed = False
    hooks = settings.setdefault("hooks", {})
    for event, groups in snippet.get("hooks", {}).items():
        existing = hooks.setdefault(event, [])
        for g in groups:
            names = script_names(g)
            match = next((e for e in existing if names and names & script_names(e)), None)
            if match is None:
                existing.append(g)
                changed = True
                continue
            # already installed: widen matcher if the snippet covers more tools (upgrade path)
            want = set(filter(None, g.get("matcher", "").split("|")))
            have = set(filter(None, match.get("matcher", "").split("|")))
            if want - have:
                order = [t for t in g.get("matcher", "").split("|") if t] + sorted(have - want)
                match["matcher"] = "|".join(order)
                changed = True
    if changed or not os.path.exists(settings_path):
        os.makedirs(os.path.dirname(os.path.abspath(settings_path)), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(settings, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print("hooks merged into " + settings_path)
    else:
        print("hooks already present; no change")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
