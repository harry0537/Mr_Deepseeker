---
name: Mr_Deepseeker
description: >
  DeepSeek-powered code review, debug, and trading brain for the 5-bot algorithmic
  trading system at /home/aibot/claude/. Use when asked to: review a bot, audit code,
  debug a bot folder, find bugs, run the trading brain, get live trade decisions,
  "what should the bots do", "deepseek review", "review all bots", "audit [botname]",
  "run brain", or "trading brain". Bot registry: alpacalivebot, cdcapp, cdcex,
  sharesies, renkobot, watchdog, shared.
---

# DeepSeek Bots Skill

Two pipelines — both live in `/home/aibot/claude/shared/deepseek.py`.

## Pipeline 1 — Code Review & Debug

### Run via script (preferred)
```bash
cd /home/aibot/claude

# Review one bot
python3 /home/aibot/.claude/skills/deepseek-bots/scripts/run_review.py review alpacalivebot

# Review with extra focus
python3 /home/aibot/.claude/skills/deepseek-bots/scripts/run_review.py review cdcex "focus on Kelly sizing bugs"

# Review all bots
python3 /home/aibot/.claude/skills/deepseek-bots/scripts/run_review.py review-all

# Review subset
python3 /home/aibot/.claude/skills/deepseek-bots/scripts/run_review.py review-all alpacalivebot sharesies

# List registered bots
python3 /home/aibot/.claude/skills/deepseek-bots/scripts/run_review.py list
```

### Output
Script prints formatted report. Present to user as-is, then offer to fix critical/high bugs.

### Bot registry
| Key | Path | Focus |
|-----|------|-------|
| `alpacalivebot` | alpacalivebot/ | US stocks, Alpaca API |
| `cdcapp` | cdcapp/ | Crypto.com App swaps |
| `cdcex` | cdcex/ | Crypto.com Exchange, Kelly sizing |
| `sharesies` | sharesies/ | NZ stocks, NZX sessions |
| `renkobot` | renkobot/ | Renko chart patterns |
| `watchdog` | watchdog/ | Halt/resume, ghost cleanup |
| `shared` | shared/ | Shared lib all bots depend on |

To add a new bot: edit `BOT_REGISTRY` dict in `/home/aibot/claude/shared/deepseek.py`.

---

## Pipeline 2 — Trading Brain

See [references/trading_brain.md](references/trading_brain.md) for full TradingState construction and live data wiring.

### Quick call (mock state)
```python
import sys, datetime; sys.path.insert(0, "/home/aibot/claude")
from shared.deepseek import trading_brain, TradingState, BotStatus, BOTS

state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    regime={"regime": "BULL_TREND", "confidence": "HIGH", "deploy_mult": 1.0,
            "halt_buys": False, "strategy_bias": "momentum"},
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
- DeepSeek key auto-loaded from `/home/aibot/claude/.env` (`DEEPSEEK_API_KEY`)
- `review_all_bots()` runs 3 bots in parallel — allow ~45s for all 7
- Watchdog halted = brain skips DeepSeek entirely, returns HOLD for all bots
- Bad JSON from brain = safe HOLD returned (no crash, no trades)
- Missing API key = `EnvironmentError` with clear message at call time

## Delegate chain (deepseek.py → openrouter.py)
`shared/openrouter.py` tries providers in order — first success wins:
1. **DeepSeek** (`DEEPSEEK_API_KEY`) — primary, cheapest
2. **Ollama 480b** — local, free, slow (~30s)
3. **OpenRouter** (`OPENROUTER_API_KEY`) — paid fallback
4. **Groq** (`GROQ_API_KEY`) — fast free tier, rate limited

All four keys live in `/home/aibot/claude/.env`.
