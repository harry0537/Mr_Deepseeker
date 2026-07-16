---
name: Mr_Deepseeker
description: >
  DeepSeek-powered code review, debug, and trading brain for Python projects.
  Use when asked to: review a project, audit code, debug a folder, find bugs,
  run the trading brain, get live trade decisions, "what should the bots do",
  "deepseek review", "review all projects", "audit [name]", "run brain",
  "trading brain", "refactor this", "add type hints", "fix these bugs",
  "write tests", "generate boilerplate", "summarize this file",
  "what does this file do", "generate commit message", "offload this",
  "save my session".
---

# Mr_Deepseeker Skill

Routes mechanical code tasks to DeepSeek — preserving Claude session tokens for reasoning and architecture work.

Two pipelines — review and brain — plus a full boilerplate/generation suite.

---

## DIVISION OF LABOUR

| Task type | Who does it |
|-----------|-------------|
| Architecture decisions, tradeoffs, debugging reasoning | **Claude** |
| Reading + understanding unfamiliar files | **DeepSeek** (`summarize_file`) |
| Writing any code from scratch | **DeepSeek** (`generate`) |
| Filling out stubs / TODOs | **DeepSeek** (`expand_stub`) |
| Refactoring (rename, restructure, extract) | **DeepSeek** (`refactor`) |
| Adding type hints | **DeepSeek** (`add_type_hints`) |
| Writing tests | **DeepSeek** (`write_tests`) |
| Adding docstrings | **DeepSeek** (`write_docstrings`) |
| Bug review + audit | **DeepSeek** (`review_project`) |
| Applying bug fixes from review | **DeepSeek** (`fix_bugs`) |
| Translating to another language | **DeepSeek** (`translate`) |
| Git commit messages | **DeepSeek** (`write_commit_message`) |

---

## WORKFLOW 1 — File Understanding (SAVE TOKENS)

**Instead of reading files with Read tool, use `summarize_file` first.**

```python
from mr_deepseeker import summarize_file, load_env
load_env()

code = open("/path/to/file.py").read()
digest = summarize_file(code, filename="file.py")
print(digest)
# Work from the digest, not the 400-line file
```

Use this whenever:
- User asks "what does X do" and the file is >100 lines
- You need to understand multiple files before deciding what to change
- Exploring an unfamiliar codebase

---

## WORKFLOW 2 — Code Review + Auto-Fix

```python
from mr_deepseeker import review_project, fix_bugs, load_env
load_env()

# Step 1: review
result = review_project("/path/to/bot", context="focus on async race conditions")

# Step 2: decide which bugs to fix (Claude's reasoning layer)
critical = [b for b in result["bugs"] if b["severity"] in ("critical", "high")]

# Step 3: DeepSeek applies the fixes (do NOT write fixes manually)
src = open("/path/to/bot/main.py").read()
fixed = fix_bugs(src, critical)
open("/path/to/bot/main.py", "w").write(fixed)
```

Present review output as-is. After presenting, ask user which bugs to fix. Then use `fix_bugs`.

---

## WORKFLOW 3 — Code Generation

```python
from mr_deepseeker import generate, expand_stub, write_tests, write_docstrings, translate, load_env
load_env()

code = generate("async rate limiter using token bucket, stdlib only")
full = expand_stub(stub_code, context="use asyncio, no third-party libs")
tests = write_tests(source_code, context="mock all network calls")
documented = write_docstrings(source_code)
ts_code = translate(python_code, "TypeScript", context="idiomatic, strict types")
```

---

## WORKFLOW 4 — Mechanical Edits

```python
from mr_deepseeker import refactor, add_type_hints, write_commit_message, load_env
load_env()

new_code = refactor(src, "rename _calc_kelly to _kelly_fraction everywhere; extract lines 40-60 into helper")
typed = add_type_hints(src)

import subprocess
diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
msg = write_commit_message(diff, context="fixing the Kelly sizing bug")
print(msg)
```

---

## Pipeline 2 — Trading Brain

See [references/trading_brain.md](references/trading_brain.md) for full TradingState construction.

```python
import datetime
from mr_deepseeker import trading_brain, TradingState, BotStatus, load_env
load_env()

BOTS = ["ALPACA", "CDC_EXCH", "SHARESIES"]
state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    bots=BOTS,
    regime={"regime": "BULL_TREND", "confidence": "HIGH", "halt_buys": False},
    macro_signal={"overall": "neutral", "sources": {}},
    signals=[],
    exposure={"total": 0.0, "bot_breakdown": {b: 0.0 for b in BOTS}},
    watchdog={"halted": False, "reason": None},
    bot_statuses={b: BotStatus() for b in BOTS},
)
result = trading_brain(state)
for d in result.get("decisions", []):
    qty = d.get("quantity") or d.get("kelly_fraction", "?")
    print(f"  {d['bot']:12} {d['action']:5} {d.get('ticker','?'):10} qty={qty}  — {d.get('reason','')[:70]}")
```

---

## CLI

```bash
python3 scripts/review.py review /path/to/project
python3 scripts/review.py review /path/to/project "focus hint"
python3 scripts/review.py review-all examples/custom_registry.json
python3 scripts/review.py json /path/to/project
python3 scripts/review.py summarize /path/to/file.py
python3 scripts/review.py commit-msg
python3 scripts/review.py commit-msg "optional context hint"
```

---

## REQUIRED OUTPUT CONTRACT

Every Mr_Deepseeker task MUST return a structured JSON handoff. Do not return freeform prose to Claude.

Investigation tasks:

```json
{
  "objective": "what was investigated",
  "summary": "2-3 sentence finding",
  "root_cause": "specific cause if found, else null",
  "confidence": 0.0,
  "affected_files": ["relative/path/file.py"],
  "affected_functions": ["module.function_name"],
  "evidence": ["snippet or log line supporting the finding"],
  "recommended_actions": ["concrete action 1", "concrete action 2"],
  "risk_level": "low|medium|high|critical",
  "requires_claude_review": false,
  "handoff": null
}
```

Code tasks:

```json
{
  "files_modified": [],
  "changes_made": [],
  "tests_added": [],
  "known_risks": [],
  "rollback_strategy": "",
  "confidence": 0.0,
  "requires_claude_review": false,
  "handoff": null
}
```

`handoff`: optional next-agent recommendation ("coder" | "debugger" | "architect" |
"code-reviewer" | null) — the main session dispatches; workers never spawn agents.

Set `requires_claude_review: true` when:
- `risk_level` is "high" or "critical"
- affects trading execution, concurrency, auth, or money
- confidence < 0.6
- finding contradicts known architecture

Claude only reads this contract — NOT the raw files or logs.

## Notes
- DeepSeek key: `DEEPSEEK_API_KEY` env var or `.env` in repo root; `load_env()` also
  falls back to `~/.deepseek_key` / `~/.openrouter_key` / `~/.openai_key` / `~/.groq_key`
- Code-returning functions auto-strip markdown fences; full-file ops (`refactor`,
  `add_type_hints`, `write_docstrings`, `fix_bugs`, `expand_stub`, `translate`)
  auto-scale max_tokens to input size (cap 8192) and warn when a file is too big to
  return whole — use `fix_bugs_surgical` then
- Review bug `line` numbers are int-coerced so `fix_bugs_surgical` can locate them
- `review_all()` runs up to 3 projects in parallel — allow ~45s for 7 projects
- Fallback chain: DeepSeek → OpenRouter → Groq — one key is enough (Ollama removed, deprecated)
- Bad JSON from brain = safe HOLD returned (no crash, no trades)
- `summarize_file` is cheap (max_tokens=1024) — use liberally to save Claude context
