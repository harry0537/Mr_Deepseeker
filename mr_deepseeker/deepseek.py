#!/usr/bin/env python3
"""
Core review and trading-brain pipelines.

review_project(path)     — audit a folder of Python files
review_all(registry)     — audit multiple folders in parallel
trading_brain(state)     — real-time multi-bot trade decisions

Set DEEPSEEK_API_KEY in .env before use.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mr_deepseeker.llm_client import deepseek_ask

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = {".pyc", ".log", ".db", ".json", ".txt", ".md", ".env"}
_SKIP_DIRS = {"__pycache__", ".git", "venv", ".venv", "node_modules"}

_REVIEW_SYSTEM = """You are an expert Python code reviewer specialising in trading systems.
Analyse code for: (1) logical errors (2) race conditions (3) unhandled edge cases
(4) dead code (5) performance risks (6) reliability failures.
Output ONLY valid JSON. No markdown. No text outside the JSON object.

Return this schema:
{
  "files_reviewed": ["file.py"],
  "bugs": [
    {
      "severity": "critical|high|medium|low",
      "file": "file.py",
      "line": 42,
      "category": "race_condition|logic_error|unhandled_exception|dead_code|performance|reliability",
      "description": "What is wrong",
      "remediation": "How to fix it"
    }
  ],
  "reliability_risks": ["string"],
  "dead_code_fragments": [{"file": "f.py", "lines": "10-20", "function": "foo"}]
}"""

_BRAIN_SYSTEM = """You are a real-time trading decision engine for a multi-bot algorithmic trading system.

Rules you MUST follow:
- Output ONLY valid JSON. No text outside the JSON object.
- Max 3 total trades per decision cycle.
- Never override watchdog halt (halted=true means NO trades for any bot).
- Every decision must include a reason field.
- All prices/fractions as decimals (0.25 not 25%).

Output schema:
{
  "decisions": [
    {"bot": "BOT_NAME", "action": "BUY|SELL|HOLD", "ticker": "SPY",
     "quantity": 10, "order_type": "LIMIT", "price_offset_pct": 0.5,
     "reason": "..."}
  ],
  "no_action": ["BOT_NAME"],
  "watchdog_note": "...",
  "risk_checks": {"total_exposure_post_trade": 0.45, "regime_compliance": true}
}"""


def _load_folder(path: str | Path, max_files: int = 20) -> dict[str, str]:
    root = Path(path)
    files: dict[str, str] = {}
    for f in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        if f.suffix in _SKIP_EXTENSIONS:
            continue
        if len(files) >= max_files:
            logger.warning("Capped at %d files, skipping rest", max_files)
            break
        try:
            files[f.name] = f.read_text(errors="replace")
        except OSError as e:
            logger.warning("Could not read %s: %s", f, e)
    return files


def _build_prompt(files: dict[str, str], context: str = "") -> str:
    parts = []
    if context:
        parts.append(f"CONTEXT: {context}\n")
    parts.append("RUNTIME: Python 3.11, asyncio\n\nCODE FILES:\n")
    for name, src in files.items():
        parts.append(f"\n### {name}\n```python\n{src}\n```")
    return "".join(parts)


def _extract_objects(raw: str) -> list[dict]:
    """Stack-based extraction of complete JSON objects, handles nesting."""
    objects = []
    depth = 0
    start = None
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(raw[start:i + 1])
                    if isinstance(obj, dict) and any(
                        k in obj for k in ("description", "issue", "severity", "bugs", "decisions")
                    ):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return objects


def _parse_json(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_objects(raw)


def _normalise(parsed: Any) -> dict[str, Any]:
    """Normalise DeepSeek review output to consistent shape."""

    def _to_bug(item: dict, fallback_file: str = "") -> dict:
        loc = item.get("location", "")
        loc_file = loc.split(":")[0].split(" ")[0] if ":" in loc else ""
        return {
            "severity":    (item.get("severity") or "medium").lower(),
            "file":        item.get("file") or loc_file or fallback_file,
            "line":        item.get("line") or (loc.split(":")[1] if ":" in loc else None),
            "category":    item.get("category") or item.get("code", "logic_error"),
            "description": (item.get("description") or item.get("issue")
                            or item.get("message") or item.get("summary", "")),
            "remediation": (item.get("remediation") or item.get("fix")
                            or item.get("suggested_fix") or item.get("recommendation", "")),
        }

    bugs: list[dict] = []
    risks: list[str] = []
    files_seen: set[str] = set()

    if isinstance(parsed, dict) and ("bugs" in parsed or "files_reviewed" in parsed):
        return parsed

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                bugs.append(_to_bug(item))
                if item.get("file"):
                    files_seen.add(item["file"])
        return {"files_reviewed": sorted(files_seen), "bugs": bugs,
                "reliability_risks": [], "dead_code_fragments": []}

    if not isinstance(parsed, dict):
        return {"files_reviewed": [], "bugs": [], "reliability_risks": [], "dead_code_fragments": []}

    _CATEGORY_KEYS = ("logical_errors", "race_conditions", "unhandled_edge_cases",
                      "performance_risks", "reliability_failures", "security_issues",
                      "dead_code", "warnings", "critical", "high", "medium", "low")
    if any(k in parsed for k in _CATEGORY_KEYS):
        sev_map = {k: ("critical" if k in ("race_conditions", "security_issues") else
                       "high" if k in ("logical_errors", "reliability_failures") else
                       "medium" if k == "unhandled_edge_cases" else "low")
                   for k in _CATEGORY_KEYS}
        for cat_key in _CATEGORY_KEYS:
            for item in parsed.get(cat_key, []):
                if isinstance(item, dict):
                    # New dict — never mutate caller's data
                    merged = {"severity": sev_map.get(cat_key, "medium"), "category": cat_key, **item}
                    bugs.append(_to_bug(merged))
        for r in parsed.get("reliability_risks", []):
            risks.append(r if isinstance(r, str) else str(r))
        return {"files_reviewed": sorted(files_seen), "bugs": bugs,
                "reliability_risks": risks, "dead_code_fragments": parsed.get("dead_code", [])}

    return parsed


def review_project(path: str | Path, context: str = "", max_files: int = 20) -> dict[str, Any]:
    """
    Audit a folder of Python files with DeepSeek.

    Args:
        path:      path to directory containing .py files
        context:   optional hint (e.g. "focus on async race conditions")
        max_files: cap to avoid token overflow

    Returns:
        {
          "files_reviewed": [...],
          "bugs": [{"severity", "file", "line", "category", "description", "remediation"}],
          "reliability_risks": [...],
          "dead_code_fragments": [...]
        }
    """
    files = _load_folder(path, max_files)
    if not files:
        raise ValueError(f"No .py files found in {path}")
    logger.info("Reviewing %d files in %s", len(files), path)
    prompt = _build_prompt(files, context)
    raw = deepseek_ask(prompt, system=_REVIEW_SYSTEM, max_tokens=8192)
    return _normalise(_parse_json(raw))


def review_all(
    registry: dict[str, dict[str, str]],
    extra_context: str = "",
    max_files: int = 20,
) -> dict[str, Any]:
    """
    Review multiple project folders in parallel.

    Args:
        registry: {"name": {"path": "/abs/path", "context": "hint"}}
        extra_context: appended to every context
        max_files: per-folder cap

    Returns:
        {
          "summary": {"total_bugs": N, "critical": N, "high": N, "medium": N, "low": N},
          "projects": {"name": review_project_result}
        }
    """
    reports: dict[str, Any] = {}
    totals = {"total_bugs": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

    def _one(name: str, entry: dict) -> tuple[str, dict]:
        ctx = entry.get("context", "")
        if extra_context:
            ctx = f"{ctx} {extra_context}".strip()
        try:
            result = review_project(entry["path"], context=ctx, max_files=max_files)
            result["name"] = name
            return name, result
        except ValueError:
            raise  # bad path / no files — surface immediately, don't swallow
        except Exception as e:
            logger.error("%s failed: %s", name, e, exc_info=True)
            return name, {"error": str(e), "name": name}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_one, n, e): n for n, e in registry.items()}
        for future in as_completed(futures):
            name, report = future.result()
            reports[name] = report
            for bug in report.get("bugs", []):
                totals["total_bugs"] += 1
                sev = bug.get("severity", "low").lower()
                if sev in totals:
                    totals[sev] += 1

    return {"summary": totals, "projects": reports}


# ── Trading brain ──────────────────────────────────────────────────────────────

@dataclass
class BotStatus:
    available_capital: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    orders_pending: list[dict] = field(default_factory=list)
    last_signal: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingState:
    """
    Full system state snapshot passed to DeepSeek each decision cycle.

    regime:       market regime dict (e.g. {"regime": "BULL_TREND", "confidence": "HIGH"})
    macro_signal: macro context dict (e.g. {"overall": "bullish", "sources": {}})
    signals:      list of {bot, ticker, strength 0-1, side BUY/SELL}
    exposure:     {total: 0.0-1.0, bot_breakdown: {BOT: float}}
    bot_statuses: {BOT_NAME: BotStatus}
    watchdog:     {halted: bool, reason: str|None}
    timestamp:    ISO8601 string
    bots:         list of bot names (used for HOLD responses)
    """
    regime: dict[str, Any]
    macro_signal: dict[str, Any]
    signals: list[dict[str, Any]]
    exposure: dict[str, Any]
    bot_statuses: dict[str, BotStatus]
    watchdog: dict[str, Any]
    timestamp: str
    bots: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        statuses = {
            bot: {
                "available_capital": s.available_capital,
                "positions": s.positions,
                "orders_pending": s.orders_pending,
                **({"last_signal": s.last_signal} if s.last_signal else {}),
                **({"metadata": s.metadata} if s.metadata else {}),
            }
            for bot, s in self.bot_statuses.items()
        }
        return json.dumps({
            "timestamp": self.timestamp,
            "market_state": {
                "regime": self.regime,
                "macro_signal": self.macro_signal,
                "signals": self.signals,
                "exposure": self.exposure,
                "watchdog": self.watchdog,
            },
            "bot_statuses": statuses,
        }, indent=2)


def trading_brain(state: TradingState) -> dict[str, Any]:
    """
    Run DeepSeek trading brain. Returns decision dict.

    Safe HOLD is returned (no exception) if watchdog is halted or DeepSeek
    returns unparseable JSON.
    """
    all_bots = state.bots or list(state.bot_statuses.keys())

    if state.watchdog.get("halted"):
        return {
            "decisions": [],
            "no_action": all_bots,
            "watchdog_note": f"System halted: {state.watchdog.get('reason')}",
            "risk_checks": {},
        }

    raw = deepseek_ask(state.to_prompt(), system=_BRAIN_SYSTEM, max_tokens=1500)
    try:
        parsed = _parse_json(raw)
        if isinstance(parsed, list):
            parsed = {"decisions": parsed, "no_action": [], "watchdog_note": "", "risk_checks": {}}
        if not isinstance(parsed, dict):
            raise ValueError(f"Unexpected response type: {type(parsed)}")
        return parsed
    except Exception as e:
        logger.error("trading_brain: bad response from DeepSeek — safe HOLD. Error: %s", e)
        return {
            "decisions": [],
            "no_action": all_bots,
            "watchdog_note": f"DeepSeek returned unparseable response — safe HOLD. Error: {e}",
            "risk_checks": {},
        }
