# Mr_Deepseeker

AI-powered code review and trading decision engine built on DeepSeek. Audits Python projects for bugs, race conditions, dead code, and reliability risks — with a multi-bot trading brain that makes live trade decisions from market state.

Built as a [Claude Code](https://claude.ai/code) skill for an algorithmic trading system. Works standalone too.

---

## What it does

### Code Review
Point it at any Python project folder. DeepSeek reads every `.py` file and returns a structured bug report — severity-ranked, with file/line references and remediation hints.

```
[CRITICAL] order_manager.py:87  [race_condition]
    Position update and order submission are not atomic — parallel fills can double-count
    FIX: Use asyncio.Lock() around the position update + order submission block

[HIGH]     risk_engine.py:134  [logic_error]
    Kelly fraction not clamped — can return >1.0 on high-confidence signals
    FIX: fraction = min(kelly_fraction, max_kelly) before returning
```

### Trading Brain
Feed it a snapshot of your system state (regime, exposure, bot positions, signals). DeepSeek returns buy/sell decisions for each bot, respecting risk rules you define.

---

## Install

```bash
git clone https://github.com/yourusername/Mr_Deepseeker.git
cd Mr_Deepseeker
cp .env.example .env
# Add your DEEPSEEK_API_KEY to .env
```

No dependencies beyond Python 3.11+ stdlib. DeepSeek API is cheap — code reviews cost ~$0.01 each.

Get a DeepSeek key at [platform.deepseek.com](https://platform.deepseek.com).

---

## Usage

### CLI — review a project

```bash
# Review a single folder
python scripts/review.py review /path/to/your/project

# With focus hint
python scripts/review.py review /path/to/your/project "focus on async race conditions"

# Raw JSON output
python scripts/review.py json /path/to/your/project

# Review multiple projects from a registry file
python scripts/review.py review-all examples/custom_registry.json
```

### Python API

```python
from mr_deepseeker import review_project, review_all

# Single folder
result = review_project("/path/to/your/bot", context="focus on API timeout handling")

for bug in result["bugs"]:
    print(f"[{bug['severity'].upper()}] {bug['file']}:{bug.get('line','')} — {bug['description']}")

# Multiple folders in parallel
registry = {
    "my_bot":   {"path": "/path/to/bot",    "context": "trading bot, focus on order logic"},
    "shared":   {"path": "/path/to/shared", "context": "shared lib"},
}
report = review_all(registry)
print(f"Total bugs: {report['summary']['total_bugs']}")
```

### Trading Brain

```python
from mr_deepseeker import trading_brain, BotStatus, TradingState
import datetime

state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    bots=["ALPACA", "CDC_EXCH"],
    regime={"regime": "BULL_TREND", "confidence": "HIGH", "halt_buys": False},
    macro_signal={"overall": "neutral", "sources": {}},
    signals=[{"bot": "ALPACA", "ticker": "SPY", "strength": 0.72, "side": "BUY"}],
    exposure={"total": 0.35, "bot_breakdown": {"ALPACA": 0.2, "CDC_EXCH": 0.15}},
    watchdog={"halted": False, "reason": None},
    bot_statuses={
        "ALPACA":   BotStatus(available_capital=45000, positions={"SPY": 50}),
        "CDC_EXCH": BotStatus(available_capital=20000),
    },
)

result = trading_brain(state)
for d in result["decisions"]:
    print(f"{d['bot']} → {d['action']} {d.get('ticker','')} qty={d.get('quantity','?')}")
#   ALPACA → BUY SPY qty=12
```

See `examples/trading_brain_example.py` for a full working example.

---

## Claude Code Skill

If you use [Claude Code](https://claude.ai/code), install Mr_Deepseeker as a skill so Claude can run reviews and the trading brain directly from chat.

```bash
# Copy the skill into your Claude skills directory
cp -r claude_skill ~/.claude/skills/Mr_Deepseeker
```

Then in Claude Code:
> *"review my alpacabot"* → Claude runs DeepSeek review and presents the report  
> *"run the trading brain"* → Claude builds TradingState from live data and calls the brain  
> *"audit all bots"* → Claude runs review_all in parallel across all registered folders

Edit `claude_skill/SKILL.md` to update bot registry paths and trigger phrases for your setup.

---

## LLM fallback chain

If DeepSeek is unavailable, Mr_Deepseeker automatically tries (in order):
1. **DeepSeek** — primary, cheapest, best for code
2. **Ollama** (local) — free, runs on your machine if you have it
3. **OpenRouter** — free tier models as backup
4. **Groq** — fast free tier, rate limited

Set whichever keys you have in `.env`. One is enough.

---

## Project structure

```
mr_deepseeker/
├── deepseek.py       # review_project(), review_all(), trading_brain()
└── llm_client.py     # LLM delegation with fallback chain

scripts/
└── review.py         # CLI runner

claude_skill/
├── SKILL.md          # Claude Code skill definition
└── references/
    └── trading_brain.md  # TradingState construction reference

examples/
├── custom_registry.json      # multi-project registry template
└── trading_brain_example.py  # full brain example with mock state
```

---

## Output schema

```json
{
  "files_reviewed": ["order_manager.py", "risk_engine.py"],
  "bugs": [
    {
      "severity": "critical",
      "file": "order_manager.py",
      "line": 87,
      "category": "race_condition",
      "description": "Position update and order submission are not atomic",
      "remediation": "Use asyncio.Lock() around the update block"
    }
  ],
  "reliability_risks": ["No circuit breaker on API failures"],
  "dead_code_fragments": [{"file": "utils.py", "lines": "45-60", "function": "old_formatter"}]
}
```

---

## License

MIT
