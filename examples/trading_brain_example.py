#!/usr/bin/env python3
"""
Example: run trading_brain() with mock state.
Replace regime/exposure/bot_statuses with real data from your system.
"""
import sys, os, datetime
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))
from mr_deepseeker import trading_brain, BotStatus, TradingState

BOTS = ["ALPACA", "CDC_APP", "CDC_EXCH", "SHARESIES", "RENKO"]

state = TradingState(
    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    bots=BOTS,
    regime={
        "regime": "BULL_TREND",
        "confidence": "HIGH",
        "deploy_mult": 1.0,
        "halt_buys": False,
        "strategy_bias": "momentum",
    },
    macro_signal={"overall": "neutral", "sources": {}},
    signals=[
        {"bot": "ALPACA", "ticker": "SPY", "strength": 0.72, "side": "BUY"},
        {"bot": "CDC_EXCH", "ticker": "BTC-USDT", "strength": 0.65, "side": "BUY"},
    ],
    exposure={"total": 0.35, "bot_breakdown": {b: 0.07 for b in BOTS}},
    watchdog={"halted": False, "reason": None},
    bot_statuses={
        "ALPACA":   BotStatus(available_capital=45000, positions={"SPY": 50}),
        "CDC_APP":  BotStatus(available_capital=5000),
        "CDC_EXCH": BotStatus(available_capital=20000, positions={"BTC-USDT": 0.3}),
        "SHARESIES": BotStatus(available_capital=8000),
        "RENKO":    BotStatus(available_capital=10000, last_signal="BUY_ETH"),
    },
)

result = trading_brain(state)

print("\n=== Trading Brain Decisions ===\n")
for d in result.get("decisions", []):
    qty = d.get("quantity") or d.get("kelly_fraction", "?")
    print(f"  {d['bot']:12} {d['action']:5} {d.get('ticker','?'):12} qty={qty}")
    print(f"    Reason: {d.get('reason','')[:80]}")
for bot in result.get("no_action", []):
    print(f"  {bot:12} HOLD")
if result.get("watchdog_note"):
    print(f"\n  Watchdog: {result['watchdog_note']}")
