"""SQLite canonical store. [YouTuber #2 pattern: store everything to one db.]

The JSONL journals stay the human-readable source of truth for trades and
hypotheses. THIS db is the analytics/observation mirror: chain snapshots,
valuations, macro scores, cached news, and fired alerts — so you can query
e.g. "every time IV jumped >20% the day before a winning trade."
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "monitor.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    asof TEXT, ticker TEXT, strike REAL, expiry TEXT, is_call INTEGER,
    bid REAL, ask REAL, last REAL, iv REAL, volume INTEGER, open_interest INTEGER,
    mark REAL, PRIMARY KEY (asof, ticker, strike, expiry, is_call)
);
CREATE TABLE IF NOT EXISTS valuations (
    asof TEXT, ticker TEXT, strike REAL, expiry TEXT, is_call INTEGER,
    mark REAL, value REAL, unreal_pnl REAL, unreal_pnl_pct REAL, dte INTEGER,
    delta REAL, gamma REAL, theta_day REAL, vega REAL, iv REAL,
    progress_to_target REAL, progress_to_stop REAL,
    PRIMARY KEY (asof, ticker, strike, expiry, is_call)
);
CREATE TABLE IF NOT EXISTS macro_scores (
    asof TEXT PRIMARY KEY, score REAL, vix REAL, vix_pctile REAL,
    term_structure REAL, breadth REAL, credit REAL, regime TEXT
);
CREATE TABLE IF NOT EXISTS news_analysis (
    asof TEXT, ticker TEXT, summary TEXT, sentiment TEXT, key_drivers TEXT,
    position_flag INTEGER, PRIMARY KEY (asof, ticker)
);
CREATE TABLE IF NOT EXISTS alerts (
    asof TEXT, ticker TEXT, kind TEXT, severity TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS iv_history (
    asof TEXT, ticker TEXT, strike REAL, expiry TEXT, is_call INTEGER, iv REAL,
    PRIMARY KEY (asof, ticker, strike, expiry, is_call)
);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def iv_rank(conn, ticker, strike, expiry, is_call, current_iv, lookback_days=252,
            min_history=20):
    """IV rank from your OWN stored snapshots. [YT#2] Returns (rank_pct, label).

    Until min_history days exist, label == 'building history' and rank is None.
    """
    rows = conn.execute(
        """SELECT iv FROM iv_history
           WHERE ticker=? AND strike=? AND expiry=? AND is_call=?
           ORDER BY asof DESC LIMIT ?""",
        (ticker, strike, expiry, int(is_call), lookback_days),
    ).fetchall()
    ivs = [r["iv"] for r in rows if r["iv"] is not None]
    if len(ivs) < min_history:
        return None, "building history"
    lo, hi = min(ivs), max(ivs)
    if hi == lo:
        return 50.0, "flat"
    rank = 100.0 * (current_iv - lo) / (hi - lo)
    label = "rich" if rank > 70 else "cheap" if rank < 30 else "mid"
    return round(rank, 1), label


if __name__ == "__main__":
    c = connect()
    print(f"monitor.db ready at {DB_PATH}")
    print("tables:", [r["name"] for r in
                      c.execute("SELECT name FROM sqlite_master WHERE type='table'")])
