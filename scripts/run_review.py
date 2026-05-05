#!/usr/bin/env python3
"""Runner script for Mr_Deepseeker skill. Called by Claude via Bash."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mr_deepseeker import review_project, review_all, load_env

load_env()


def print_report(result: dict, label: str = ""):
    label = label or "ALL PROJECTS"

    # review_all output
    if "summary" in result:
        s = result["summary"]
        print(f"\n{'='*60}")
        print(f"DEEPSEEK REVIEW — {label}")
        print(f"{'='*60}")
        print(f"Total: {s['total_bugs']}  |  critical={s['critical']}  high={s['high']}  medium={s['medium']}  low={s['low']}")
        for name, report in result["projects"].items():
            if "error" in report:
                print(f"\n  [{name}] ERROR: {report['error']}")
                continue
            bugs = report.get("bugs", [])
            print(f"\n  ── {name} ({len(bugs)} issues) ──")
            for b in bugs:
                line = f":{b['line']}" if b.get("line") else ""
                print(f"    [{b['severity'].upper():8}] {b['file']}{line}")
                print(f"             {b['description'][:90]}")
                if b.get("remediation"):
                    print(f"             FIX: {b['remediation'][:80]}")
        return

    # single review_project output
    bugs = result.get("bugs", [])
    risks = result.get("reliability_risks", [])
    dead = result.get("dead_code_fragments", [])

    print(f"\n{'='*60}")
    print(f"DEEPSEEK REVIEW — {label}")
    print(f"{'='*60}")
    print(f"Files: {', '.join(result.get('files_reviewed', []))}")

    sev_order = ["critical", "high", "medium", "low"]
    by_sev = {s: [b for b in bugs if b["severity"].lower() == s] for s in sev_order}

    for sev in sev_order:
        group = by_sev[sev]
        if not group:
            continue
        print(f"\n[{sev.upper()}] — {len(group)} issue(s)")
        for b in group:
            line = f":{b['line']}" if b.get("line") else ""
            print(f"  {b['file']}{line}  [{b.get('category','?')}]")
            print(f"    {b['description']}")
            if b.get("remediation"):
                print(f"    FIX: {b['remediation']}")

    if risks:
        print(f"\n[RELIABILITY RISKS]")
        for r in risks:
            print(f"  • {r}")

    if dead:
        print(f"\n[DEAD CODE]")
        for d in dead:
            print(f"  {d.get('file','?')} {d.get('lines','?')} — {d.get('function','?')}")

    print(f"\nSummary: {len(bugs)} bugs  ({sum(len(by_sev[s]) for s in ['critical','high'])} critical/high)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "help":
        print("Usage:")
        print("  python run_review.py review <path> [context]")
        print("  python run_review.py review-all <registry.json>")
        print("  python run_review.py json <path>")

    elif cmd == "review":
        path = sys.argv[2]
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        result = review_project(path, context=context)
        print_report(result, Path(path).name)

    elif cmd == "review-all":
        registry_path = sys.argv[2]
        with open(registry_path) as f:
            registry = json.load(f)
        result = review_all(registry)
        print_report(result)

    elif cmd == "json":
        path = sys.argv[2]
        result = review_project(path)
        print(json.dumps(result, indent=2))
