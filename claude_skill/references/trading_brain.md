# Trading Brain Reference

## When to use
Call `trading_brain()` when the user asks for live trade decisions, "run the brain", "what should the bots do", or wants a decision cycle.

## Fallback data — when live sources fail
```python
# Regime fallback
try:
    from shared.regime_builder import get_regime, RegimeInput
    regime = get_regime(RegimeInput(market="stocks")).to_dict()
except Exception:
    regime = {"regime": "UNKNOWN", "confidence": "LOW", "deploy_mult": 0.5,
              "halt_buys": True, "strategy_bias": "defensive"}

# Coord fallback
try:
    from shared.coord import load_state as load_coord
    coord = load_coord()
except Exception:
    coord = {}

# Exposure fallback
try:
    from shared.exposure import SystemExposure
    exp = SystemExposure.load()
    exposure = {"total": exp.total, "bot_breakdown": exp.by_bot}
except Exception:
    exposure = {"total": 0.0, "bot_breakdown": {b: 0.0 for b in BOTS}}

# Watchdog fallback
try:
    import os
    wstate = json.load(open("/home/aibot/claude/watchdog/state.json")) \
        if os.path.exists("/home/aibot/claude/watchdog/state.json") \
        else {"halted": False, "reason": None}
except Exception:
    wstate = {"halted": False, "reason": None}
```

If `trading_brain()` returns unparseable JSON, it now auto-returns `HOLD` for all bots instead of raising.

## Building TradingState

Pull live data from these sources in `/home/aibot/claude/`:

```python
import sys, datetime
sys.path.insert(0, "/home/aibot/claude")

from shared.deepseek import trading_brain, TradingState, BotStatus, BOTS
from shared.regime_builder import get_regime, RegimeInput
from shared.coord import load_coord          # bot capital + positions
from shared.exposure import get_exposure     # total exposure float
```

### Minimal working state (when live data unavailable)
```python
state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    regime={"regime": "BULL_TREND", "confidence": "HIGH", "deploy_mult": 1.0,
            "halt_buys": False, "strategy_bias": "momentum"},
    macro_signal={"overall": "neutral", "sources": {}},
    signals=[],  # populate from signal_scanner if available
    exposure={"total": 0.0, "bot_breakdown": {b: 0.0 for b in BOTS}},
    watchdog={"halted": False, "reason": None},
    bot_statuses={b: BotStatus() for b in BOTS},
)
result = trading_brain(state)
```

### Full state with live data
```python
# 1. Regime
from shared.regime_builder import get_regime, RegimeInput
regime_out = get_regime(RegimeInput(market="stocks"))  # or "crypto"
regime = regime_out.to_dict()

# 2. Coord (capital + positions per bot)
from shared.coord import load_state as load_coord
coord = load_coord()  # returns dict keyed by bot name

# 3. Exposure
from shared.exposure import SystemExposure
exp = SystemExposure.load()
exposure = {"total": exp.total, "bot_breakdown": exp.by_bot}

# 4. Watchdog
import json
wstate = json.load(open("/home/aibot/claude/watchdog/state.json")) \
    if os.path.exists("/home/aibot/claude/watchdog/state.json") \
    else {"halted": False, "reason": None}

# 5. Assemble
bot_statuses = {}
for bot in BOTS:
    c = coord.get(bot, {})
    bot_statuses[bot] = BotStatus(
        available_capital=c.get("cash", 0),
        positions=c.get("positions", {}),
    )

state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    regime=regime,
    macro_signal={"overall": "neutral", "sources": {}},
    signals=[],
    exposure=exposure,
    watchdog=wstate,
    bot_statuses=bot_statuses,
)
result = trading_brain(state)
```

## Output format
```json
{
  "decisions": [
    {"bot": "ALPACA", "action": "BUY", "ticker": "SPY",
     "quantity": 10, "order_type": "LIMIT", "price_offset_pct": 0.5,
     "reason": "..."}
  ],
  "no_action": ["CDC_APP", "SHARESIES"],
  "watchdog_note": "...",
  "risk_checks": {"total_exposure_post_trade": 0.45, "regime_compliance": true}
}
```

## Display decisions
```python
for d in result.get("decisions", []):
    action = d.get("action", "?")
    ticker = d.get("ticker", "?")
    qty = d.get("quantity") or d.get("kelly_fraction", "?")
    print(f"  {d['bot']:12} {action:5} {ticker:10} qty={qty}  — {d.get('reason','')[:70]}")
for bot in result.get("no_action", []):
    print(f"  {bot:12} HOLD")
```
