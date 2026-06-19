"""Expectancy scoring — the LEARN layer's objective metric.

Reads journal/trades.jsonl and computes the number goal.yaml optimizes for:
    EXPECTANCY = (win_rate * avg_win_$) - (loss_rate * avg_loss_$)

trades.jsonl row schema (one JSON object per line):
    trade_id        str   uuid
    ts_entry        str   ISO 8601
    ts_exit         str   ISO 8601 (omit/null while open)
    ticker          str
    side            str   "call" | "put"
    strike          float
    expiry          str   YYYY-MM-DD
    premium_paid    float per contract
    contracts       int
    cost_usd        float contracts * premium_paid * 100
    exit_price      float per contract (null while open)
    exit_reason     str   tp_hit|stop_hit|invalidation|time_stop|manual_close
    pnl_usd         float
    pnl_pct         float vs cost basis
    regime          str   trend_up|trend_down|chop|event_driven
    gates_passed    list  e.g. ["macro","a_plus","concentration","gut"]
    strategy_version str  which strategy.yaml version was active
    hypothesis_id   str   which weekly hypothesis this trade tests
    notes           str
"""
from __future__ import annotations

import json
from pathlib import Path

TRADES = Path(__file__).resolve().parent.parent / "journal" / "trades.jsonl"


def load_closed(path: Path | str = TRADES):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("ts_exit") and row.get("pnl_usd") is not None:
            out.append(row)
    return out


def expectancy(trades):
    """Returns a stats dict. Empty-safe."""
    n = len(trades)
    if n == 0:
        return {"n": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "expectancy": 0.0, "total_pnl": 0.0}
    wins = [t["pnl_usd"] for t in trades if t["pnl_usd"] > 0]
    losses = [-t["pnl_usd"] for t in trades if t["pnl_usd"] <= 0]  # positive magnitudes
    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    exp = win_rate * avg_win - loss_rate * avg_loss
    return {
        "n": n,
        "win_rate": round(win_rate, 3),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(exp, 2),
        "total_pnl": round(sum(t["pnl_usd"] for t in trades), 2),
    }


def by_regime(trades):
    groups = {}
    for t in trades:
        groups.setdefault(t.get("regime", "unknown"), []).append(t)
    return {regime: expectancy(g) for regime, g in groups.items()}


def report(path: Path | str = TRADES):
    trades = load_closed(path)
    overall = expectancy(trades)
    print(f"Closed trades: {overall['n']}  |  Win rate: {overall['win_rate']*100:.0f}%")
    print(f"Avg win ${overall['avg_win']}  |  Avg loss ${overall['avg_loss']}")
    print(f"EXPECTANCY: ${overall['expectancy']}/trade  |  Total P&L ${overall['total_pnl']}")
    print("\nBy regime:")
    for regime, s in by_regime(trades).items():
        print(f"  {regime:14s} n={s['n']:2d}  win={s['win_rate']*100:3.0f}%  "
              f"exp=${s['expectancy']}")
    return overall


if __name__ == "__main__":
    report()
