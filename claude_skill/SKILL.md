---
name: Mr_Deepseeker
description: >
  DeepSeek-powered code review, debug, and trading brain for Python projects.
  Use when asked to: review a project, audit code, debug a folder, find bugs,
  run the trading brain, get live trade decisions, "what should the bots do",
  "deepseek review", "review all projects", "audit [name]", "run brain",
  or "trading brain".
---

# Mr_Deepseeker Skill

Two pipelines — review and brain — both in `mr_deepseeker/deepseek.py`.

## Setup

1. Clone: `git clone https://github.com/yourusername/Mr_Deepseeker`
2. Copy skill: `cp -r claude_skill ~/.claude/skills/Mr_Deepseeker`
3. Set `DEEPSEEK_API_KEY` in `.env`

## Pipeline 1 — Code Review & Debug

### Run via script (preferred)
```bash
# Review one project folder
python scripts/review.py review /path/to/project

# Review with extra focus
python scripts/review.py review /path/to/project "focus on Kelly sizing bugs"

# Review all from registry
python scripts/review.py review-all examples/custom_registry.json

# Raw JSON output
python scripts/review.py json /path/to/project
```

### Python API
```python
from mr_deepseeker import review_project, review_all

result = review_project("/path/to/project", context="focus on async race conditions")
for bug in result["bugs"]:
    print(f"[{bug['severity']}] {bug['file']}:{bug.get('line','')} — {bug['description']}")
```

### Output
Script prints formatted report. Present to user as-is, then offer to fix critical/high bugs.

### Registry format
```json
{
  "my_bot": {"path": "/abs/path/to/bot", "context": "trading bot, focus on order logic"},
  "shared":  {"path": "/abs/path/to/shared", "context": "shared library"}
}
```

---

## Pipeline 2 — Trading Brain

See [references/trading_brain.md](references/trading_brain.md) for full TradingState construction.

### Quick call (mock state)
```python
import datetime
from mr_deepseeker import trading_brain, TradingState, BotStatus

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
for bot in result.get("no_action", []):
    print(f"  {bot:12} HOLD")
```

---

## Notes
- DeepSeek key loaded from `DEEPSEEK_API_KEY` env var (or `.env` in project root)
- `review_all()` runs up to 3 projects in parallel — allow ~45s for 7 projects
- Watchdog halted = brain skips DeepSeek entirely, returns HOLD for all bots
- Bad JSON from brain = safe HOLD returned (no crash, no trades)
- Missing API key = `RuntimeError` with clear message at call time

## LLM fallback chain
1. **DeepSeek** (`DEEPSEEK_API_KEY`) — primary, cheapest
2. **Ollama** (local) — free, requires Ollama running locally
3. **OpenRouter** (`OPENROUTER_API_KEY`) — free tier models
4. **Groq** (`GROQ_API_KEY`) — fast free tier, rate limited
