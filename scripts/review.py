#!/usr/bin/env python3
"""
Mr_Deepseeker CLI — review Python projects with DeepSeek AI.

Usage:
    python scripts/review.py review /path/to/project
    python scripts/review.py review /path/to/project "focus on async race conditions"
    python scripts/review.py review-all registry.json
    python scripts/review.py json /path/to/project      # raw JSON output
"""
import sys
import json
import os
from pathlib import Path

# Load .env from repo root
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))
from mr_deepseeker import review_project, review_all


def print_report(result: dict, label: str = "") -> None:
    label = label or result.get("name", "PROJECT")

    # review_all output
    if "summary" in result and "projects" in result:
        s = result["summary"]
        print(f"\n{'='*60}")
        print(f"MR_DEEPSEEKER REVIEW — ALL PROJECTS")
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
    print(f"MR_DEEPSEEKER REVIEW — {label.upper()}")
    print(f"{'='*60}")
    print(f"Files: {', '.join(result.get('files_reviewed', []))}")

    for sev in ("critical", "high", "medium", "low"):
        group = [b for b in bugs if b.get("severity", "").lower() == sev]
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

    crit_high = sum(1 for b in bugs if b.get("severity","").lower() in ("critical","high"))
    print(f"\nSummary: {len(bugs)} bugs  ({crit_high} critical/high)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd in ("help", "--help", "-h") or len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)

    elif cmd == "review":
        path = sys.argv[2]
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        result = review_project(path, context=context)
        print_report(result, label=Path(path).name)

    elif cmd == "review-all":
        registry_path = sys.argv[2]
        registry = json.loads(Path(registry_path).read_text())
        result = review_all(registry)
        print_report(result)

    elif cmd == "json":
        path = sys.argv[2]
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        result = review_project(path, context=context)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
