# Trading Brain Reference

## When to use
Call `trading_brain()` when the user asks for live trade decisions, "run the brain", "what should the bots do", or wants a decision cycle.

## Building TradingState

```python
import datetime
from mr_deepseeker import trading_brain, TradingState, BotStatus

# Define your bots
BOTS = ["ALPACA", "CDC_APP", "CDC_EXCH", "SHARESIES", "RENKO"]

# Pull regime from your regime engine (or use a static fallback)
regime = {
    "regime": "BULL_TREND",     # BULL_TREND | BEAR_TREND | SIDEWAYS | etc.
    "confidence": "HIGH",        # HIGH | MEDIUM | LOW
    "deploy_mult": 1.0,          # capital multiplier
    "halt_buys": False,
    "strategy_bias": "momentum", # momentum | defensive | neutral
}

# Pull macro signal from your intel source (or use a static fallback)
macro_signal = {"overall": "neutral", "sources": {}}

# Pull signals from your signal scanner
signals = [
    {"bot": "ALPACA", "ticker": "SPY", "strength": 0.72, "side": "BUY"},
    {"bot": "CDC_EXCH", "ticker": "BTC-USDT", "strength": 0.65, "side": "BUY"},
]

# Pull exposure from your tracking layer
exposure = {
    "total": 0.35,
    "bot_breakdown": {b: 0.07 for b in BOTS},
}

# Pull watchdog state
watchdog = {"halted": False, "reason": None}

# Build per-bot status
bot_statuses = {
    "ALPACA":    BotStatus(available_capital=45000, positions={"SPY": 50}),
    "CDC_APP":   BotStatus(available_capital=5000),
    "CDC_EXCH":  BotStatus(available_capital=20000, positions={"BTC-USDT": 0.3}),
    "SHARESIES": BotStatus(available_capital=8000),
    "RENKO":     BotStatus(available_capital=10000, last_signal="BUY_ETH"),
}

state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    bots=BOTS,
    regime=regime,
    macro_signal=macro_signal,
    signals=signals,
    exposure=exposure,
    watchdog=watchdog,
    bot_statuses=bot_statuses,
)

result = trading_brain(state)
```

## Fallback data — when live sources fail

```python
# Regime fallback
try:
    regime = get_regime_from_your_engine()
except Exception:
    regime = {"regime": "UNKNOWN", "confidence": "LOW", "deploy_mult": 0.5,
              "halt_buys": True, "strategy_bias": "defensive"}

# Watchdog fallback
import json, os
try:
    watchdog_path = "/path/to/your/watchdog/state.json"
    watchdog = json.load(open(watchdog_path)) if os.path.exists(watchdog_path) else {"halted": False, "reason": None}
except Exception:
    watchdog = {"halted": False, "reason": None}
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
