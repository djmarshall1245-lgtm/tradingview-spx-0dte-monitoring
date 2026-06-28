"""Terminal engine for SPX 0DTE signal monitoring + execution.

Polls TradingView MCP (via Claude Code) for AR Squeeze dashboard state,
detects triggers, freezes for manual approval, then routes orders through
Robinhood MCP. NEVER auto-fires — two human gates are sacred.

This module provides the state machine + parsing + journaling. The actual
MCP tool calls happen in the caller (Claude Code session or a wrapper
script that speaks MCP stdio). The engine is the brain; the caller is
the hands.

Source of truth: strategy/strategy.yaml → terminal_engine section.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
STRATEGY_PATH = ROOT / "strategy" / "strategy.yaml"
JOURNAL_PATH = ROOT / "journal" / "trades.jsonl"


# ── Config loader ────────────────────────────────────────────────────

def load_strategy() -> dict:
    """Load strategy.yaml, return the full dict."""
    return yaml.safe_load(STRATEGY_PATH.read_text())


def load_engine_config(strategy: dict | None = None) -> dict:
    """Return the terminal_engine section + resolved inherited values."""
    strategy = strategy or load_strategy()
    eng = strategy["terminal_engine"]

    # Resolve inherited values from the parent strategy
    eng["_resolved"] = {
        "hard_stop_pct": strategy["exits"]["hard_stop_pct"],
        "daily_cap": strategy["risk_controls"]["daily_loss_cap_trades"],
        "order_type": strategy["execution"]["order_type"],
        "max_positions": strategy["concurrency"]["max_open_positions"],
        "premium_band": strategy["instrument"]["premium_per_contract_usd"],
    }
    return eng


# ── State machine ────────────────────────────────────────────────────

class Phase(Enum):
    IDLE = "idle"               # polling, no signal
    TRIGGERED = "triggered"     # signal fired, awaiting gate #1 (trade GO)
    PREVIEWING = "previewing"   # order previewed, awaiting gate #2 (order GO)
    IN_TRADE = "in_trade"       # position open, monitoring exits
    DONE = "done"               # daily cap hit or session over


@dataclass
class DashboardSnapshot:
    """Parsed AR Squeeze dashboard state from data_get_pine_tables."""
    signal: str = "WATCH"           # TREND / SCALP / EARLY / WATCH
    direction: str = ""             # CALL / PUT
    close: float = 0.0              # SPX price
    tick_ma: float = 0.0            # $TICK 5MA
    tlt_chg: float = 0.0            # TLT intraday %
    tlt_thresh: float = 0.0         # TLT threshold from Pine
    confluence: int = 0             # x/6
    squeeze_state: str = ""         # squeeze firing / momentum
    time_window: str = ""           # ACTIVE / LUNCH / CLOSE OUT / WAIT
    call_confirm: bool = False
    put_confirm: bool = False
    call_trend: bool = False
    call_scalp: bool = False
    put_trend: bool = False
    put_scalp: bool = False
    call_early: bool = False
    put_early: bool = False
    exit_call: bool = False
    exit_put: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class VoodooLevels:
    """Voodoo pivot levels parsed from data_get_pine_labels."""
    r3: float = 0.0
    r2: float = 0.0
    r1: float = 0.0
    pp: float = 0.0
    s1: float = 0.0
    s2: float = 0.0
    s3: float = 0.0


@dataclass
class EngineState:
    """Mutable state for one trading day."""
    phase: Phase = Phase.IDLE
    trades_today: int = 0
    losses_today: int = 0
    daily_cap: int = 2
    last_trigger_bar: int = 0       # prevent re-prompt on same candle
    current_position: dict = field(default_factory=dict)
    last_snapshot: Optional[DashboardSnapshot] = None
    last_voodoo: Optional[VoodooLevels] = None
    reject_cooldown_until: float = 0.0  # unix timestamp

    def can_trade(self) -> tuple[bool, str]:
        """Check if another trade is allowed today."""
        if self.trades_today >= self.daily_cap:
            return False, f"daily cap hit ({self.trades_today}/{self.daily_cap})"
        if self.losses_today >= 2:
            return False, f"2 losses today — done"
        return True, "ok"


# ── Dashboard parser ─────────────────────────────────────────────────

def parse_dashboard(table_data) -> DashboardSnapshot:
    """Parse the AR Squeeze dashboard from data_get_pine_tables output.

    Handles two formats:
    1. Flat strings: ["SPX: 7354.03", "$TICK 5MA: 237", "SCALP MODE"]
       (this is what the MCP actually returns via the rows list)
    2. Dict rows: [{"col0": "SPX", "col1": "7354.03"}, ...]
       (fallback if Pine table format changes)

    Signal text like "CALL TREND", "SCALP MODE", "PUT SCALP" is mapped
    to the boolean trigger fields since Pine internal variables (callConfirm,
    etc.) aren't directly exposed in the rendered table.
    """
    snap = DashboardSnapshot()
    snap.raw = table_data

    # ── Step 1: normalize everything into a cells dict ────────────────
    cells = {}
    standalone_tokens = []  # rows with no colon (e.g. "SCALP MODE")

    for item in table_data:
        text = ""
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            # Dict row — join all values
            text = " ".join(str(v).strip() for v in item.values()).strip()

        if not text:
            continue

        # Try to split on first colon → label: value
        if ":" in text:
            label, _, value = text.partition(":")
            label = label.strip().lower()
            value = value.strip()
            # Normalize common label variants
            label = label.replace("$", "").replace("%", "pct")
            cells[label] = value
        else:
            standalone_tokens.append(text.upper())

    # ── Step 2: extract numeric fields ────────────────────────────────
    snap.close = _float(cells, ["spx", "close", "price", "entry"])
    snap.tick_ma = _float(cells, ["tick 5ma", "tick_ma", "tick", "tick5ma"])
    snap.tlt_chg = _float(cells, ["tlt pctchg", "tlt chg", "tlt_chg", "tlt",
                                   "tlt change", "tlt pct chg"])
    snap.tlt_thresh = _float(cells, ["tlt_thresh", "tltthresh", "tlt threshold"])
    snap.confluence = int(_float(cells, ["confluence", "conf"]))
    snap.squeeze_state = _str(cells, ["squeeze", "squeeze_state", "sqz"])
    snap.time_window = _str(cells, ["time_window", "time window", "time",
                                     "window"]).upper()

    # ── Step 3: map signal text to booleans ───────────────────────────
    # The dashboard renders the signal as a text row (e.g. "CALL TREND",
    # "SCALP MODE", "PUT SCALP", "EARLY", "WATCH"). We parse these into
    # the confirm/trend/scalp/early booleans the engine expects.
    #
    # Also check the cells dict for an explicit "signal" key.
    signal_text = _str(cells, ["signal", "sig"]).upper()
    if not signal_text:
        signal_text = " ".join(standalone_tokens)

    snap.signal = _classify_signal(signal_text)

    # Derive direction + type booleans from signal text
    sig = signal_text.upper()

    if "CALL" in sig and "TREND" in sig:
        snap.call_confirm = True
        snap.call_trend = True
        snap.direction = "CALL"
    elif "PUT" in sig and "TREND" in sig:
        snap.put_confirm = True
        snap.put_trend = True
        snap.direction = "PUT"
    elif "CALL" in sig and "SCALP" in sig:
        snap.call_confirm = True
        snap.call_scalp = True
        snap.direction = "CALL"
    elif "PUT" in sig and "SCALP" in sig:
        snap.put_confirm = True
        snap.put_scalp = True
        snap.direction = "PUT"
    elif "SCALP" in sig and "MODE" in sig:
        # "SCALP MODE" without direction = scalp regime active, but no
        # confirmed direction yet. Not a trigger — need CALL/PUT qualifier.
        snap.signal = "SCALP"
    elif "CALL" in sig and "EARLY" in sig:
        snap.call_early = True
        snap.direction = "CALL"
    elif "PUT" in sig and "EARLY" in sig:
        snap.put_early = True
        snap.direction = "PUT"
    elif "EARLY" in sig:
        snap.call_early = "CALL" in sig
        snap.put_early = "PUT" in sig

    # Explicit boolean cells (if the table ever adds them)
    snap.call_confirm = snap.call_confirm or _bool(cells, ["callconfirm", "call_confirm"])
    snap.put_confirm = snap.put_confirm or _bool(cells, ["putconfirm", "put_confirm"])
    snap.exit_call = _bool(cells, ["exitcall", "exit_call", "exit call"])
    snap.exit_put = _bool(cells, ["exitput", "exit_put", "exit put"])

    return snap


def _classify_signal(text: str) -> str:
    """Map raw signal text to a canonical signal name."""
    t = text.upper()
    if "TREND" in t:
        return "TREND"
    if "SCALP" in t:
        return "SCALP"
    if "EARLY" in t:
        return "EARLY"
    return "WATCH"


def parse_voodoo(labels: list[dict]) -> VoodooLevels:
    """Parse Voodoo pivot levels from data_get_pine_labels output.

    Labels come as dicts with 'text' and 'price' fields. We match known
    level names (R1, R2, R3, S1, S2, S3, PP/Pivot).
    """
    voodoo = VoodooLevels()
    for label in labels:
        text = str(label.get("text", "")).upper().strip()
        price = label.get("price", 0)
        if not price:
            continue
        price = float(price)

        if re.match(r"^R3\b", text):
            voodoo.r3 = price
        elif re.match(r"^R2\b", text):
            voodoo.r2 = price
        elif re.match(r"^R1\b", text):
            voodoo.r1 = price
        elif re.match(r"^(PP|PIVOT)\b", text):
            voodoo.pp = price
        elif re.match(r"^S1\b", text):
            voodoo.s1 = price
        elif re.match(r"^S2\b", text):
            voodoo.s2 = price
        elif re.match(r"^S3\b", text):
            voodoo.s3 = price

    return voodoo


# ── Trigger evaluation ───────────────────────────────────────────────

@dataclass
class TriggerResult:
    fired: bool = False
    signal_type: str = ""       # "CALL TREND", "CALL SCALP", "PUT TREND", "PUT SCALP"
    direction: str = ""         # "CALL" or "PUT"
    reason_skip: str = ""       # why we didn't fire (for logging)
    is_early: bool = False      # early signal — log only


def evaluate_trigger(snap: DashboardSnapshot, state: EngineState,
                     now_ts: float = 0.0) -> TriggerResult:
    """Decide if the current dashboard snapshot constitutes a trigger.

    Returns a TriggerResult. The engine should only prompt the user if
    result.fired is True.
    """
    result = TriggerResult()

    # Check early signals (log only, never fire)
    if snap.call_early or snap.put_early:
        result.is_early = True
        result.signal_type = "CALL EARLY" if snap.call_early else "PUT EARLY"
        result.reason_skip = "EARLY signal — prep only, not actionable"
        return result

    # No confirm = no trigger
    if not snap.call_confirm and not snap.put_confirm:
        result.reason_skip = "no confirm signal"
        return result

    # Time window must be ACTIVE
    tw = snap.time_window.upper()
    if tw != "ACTIVE":
        result.reason_skip = f"time window = {tw} (need ACTIVE)"
        return result

    # Daily cap
    can, reason = state.can_trade()
    if not can:
        result.reason_skip = reason
        return result

    # Reject cooldown (same candle)
    if now_ts and now_ts < state.reject_cooldown_until:
        result.reason_skip = "reject cooldown active (same bar)"
        return result

    # Determine signal type
    if snap.call_confirm:
        result.direction = "CALL"
        if snap.call_trend:
            result.signal_type = "CALL TREND"
        elif snap.call_scalp:
            result.signal_type = "CALL SCALP"
            if snap.confluence < 3:
                result.reason_skip = f"CALL SCALP but confluence {snap.confluence}/6 < 3"
                return result
        else:
            result.reason_skip = "callConfirm but neither trend nor scalp"
            return result
    elif snap.put_confirm:
        result.direction = "PUT"
        if snap.put_trend:
            result.signal_type = "PUT TREND"
        elif snap.put_scalp:
            result.signal_type = "PUT SCALP"
            if snap.confluence < 3:
                result.reason_skip = f"PUT SCALP but confluence {snap.confluence}/6 < 3"
                return result
        else:
            result.reason_skip = "putConfirm but neither trend nor scalp"
            return result

    result.fired = True
    return result


# ── Approval prompt builder ──────────────────────────────────────────

def build_approval_prompt(snap: DashboardSnapshot, voodoo: VoodooLevels,
                          state: EngineState, config: dict) -> str:
    """Build the terminal approval prompt string."""
    resolved = config["_resolved"]
    hard_stop = resolved["hard_stop_pct"]
    daily_cap = resolved["daily_cap"]

    if snap.direction == "CALL":
        tp1, tp1_label = voodoo.r1, "R1"
        tp2, tp2_label = voodoo.r2, "R2"
        chart_stop, chart_stop_label = "prior bar low", "low[1]"
    else:
        tp1, tp1_label = voodoo.s1, "S1"
        tp2, tp2_label = voodoo.s2, "S2"
        chart_stop, chart_stop_label = "prior bar high", "high[1]"

    trigger = evaluate_trigger(snap, state)
    trade_number = state.trades_today + 1

    return f"""
============================================================
 [AR 0DTE SPX SYSTEM] - TRIGGER CONFIRMED
============================================================
TYPE:           {trigger.signal_type}
SPX Entry:      {snap.close}
$TICK 5MA:      {snap.tick_ma}  (threshold: >= 200 / <= -200)
TLT Chg:        {snap.tlt_chg}%  (threshold: {snap.tlt_thresh})
Confluence:     {snap.confluence}/6
Squeeze:        {snap.squeeze_state}
Time Window:    {snap.time_window}
------------------------------------------------------------
TARGET ARCHITECTURE (Voodoo Levels):
  TP1:          {tp1}  ({tp1_label})
  TP2:          {tp2}  ({tp2_label})
  Hard Stop:    {hard_stop}% of premium  (strategy.yaml)
  Chart Stop:   {chart_stop}  ({chart_stop_label})
------------------------------------------------------------
[ACTION]: Build 0DTE SPX single-leg {snap.direction}.
Strike guidance: ATM to 1-strike ITM (~0.45-0.55 delta)
Order type: LIMIT at mid | Account: ****3232
Trade #{trade_number} of {daily_cap} today.

Approve execution? (y/n): """


# ── Exit evaluation ──────────────────────────────────────────────────

@dataclass
class ExitSignal:
    should_exit: bool = False
    reason: str = ""


def evaluate_exit(snap: DashboardSnapshot, position: dict,
                  config: dict, now_et_hour: float = 0.0) -> ExitSignal:
    """Check whether an open position should be exited.

    position dict expects: direction (CALL/PUT), entry_premium, current_mark
    """
    direction = position.get("direction", "")
    entry_premium = position.get("entry_premium", 0)
    current_mark = position.get("current_mark", 0)
    hard_stop_pct = config["_resolved"]["hard_stop_pct"]

    # AR Squeeze exit booleans
    if direction == "CALL" and snap.exit_call:
        return ExitSignal(True, "exitCall fired")
    if direction == "PUT" and snap.exit_put:
        return ExitSignal(True, "exitPut fired")

    # Signal flip
    if direction == "CALL" and snap.put_confirm:
        return ExitSignal(True, "signal flip — putConfirm while holding CALL")
    if direction == "PUT" and snap.call_confirm:
        return ExitSignal(True, "signal flip — callConfirm while holding PUT")

    # Hard stop (P&L check)
    if entry_premium > 0 and current_mark > 0:
        pnl_pct = ((current_mark - entry_premium) / entry_premium) * 100
        if pnl_pct <= hard_stop_pct:
            return ExitSignal(True, f"hard stop hit: {pnl_pct:.1f}% <= {hard_stop_pct}%")

    # Time exit — 15:30 ET
    if now_et_hour >= 15.5:
        return ExitSignal(True, "TIME EXIT 15:30 ET — force close")

    # VWAP lost / MON EXIT would be detected from dashboard — check signal
    tw = snap.time_window.upper()
    if tw == "CLOSE OUT":
        return ExitSignal(True, "time window = CLOSE OUT")

    return ExitSignal(False, "")


# ── Journal logging ──────────────────────────────────────────────────

def log_trade(entry: dict) -> Path:
    """Append a trade entry to journal/trades.jsonl."""
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return JOURNAL_PATH


def make_trade_entry(
    ticker: str,
    direction: str,
    strike: float,
    expiry: str,
    premium_paid: float,
    contracts: int,
    signal_type: str,
    confluence: int,
    trade_number: int,
    order_id: str = "",
    notes: str = "",
) -> dict:
    """Build a journal entry dict matching the existing trades.jsonl format."""
    now = datetime.now().astimezone()
    side = "call" if direction == "CALL" else "put"
    return {
        "trade_id": f"SPX-{now.strftime('%Y%m%d')}-{trade_number:03d}",
        "ts_entry": now.isoformat(),
        "ticker": ticker,
        "side": side,
        "strike": strike,
        "expiry": expiry,
        "premium_paid": premium_paid,
        "contracts": contracts,
        "cost_usd": round(premium_paid * contracts * 100, 2),
        "regime": "0dte",
        "signal_type": signal_type,
        "confluence": confluence,
        "gates_passed": ["ar_squeeze", "time_window"],
        "gates_overridden": [],
        "strategy_version": "02",
        "order_id": order_id,
        "account": "3232",
        "notes": notes,
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _float(cells: dict, keys: list[str]) -> float:
    for k in keys:
        if k in cells:
            try:
                # Strip non-numeric chars except . and -
                cleaned = re.sub(r"[^\d.\-]", "", cells[k])
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                pass
    return 0.0


def _str(cells: dict, keys: list[str]) -> str:
    for k in keys:
        if k in cells:
            return cells[k]
    return ""


def _bool(cells: dict, keys: list[str]) -> bool:
    for k in keys:
        if k in cells:
            v = cells[k].lower()
            return v in ("true", "1", "yes", "✓", "✔")
    return False
