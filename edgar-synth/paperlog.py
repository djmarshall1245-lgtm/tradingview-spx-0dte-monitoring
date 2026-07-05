"""Phase 4: paper log. Every signal recorded; alerted ones get price fills at
+5m / +30m / +1d. This log decides whether the edge is real before money moves.

Note: after-hours filings fill with FMP last/extended price — treat p5m on
post-close 8-Ks as indicative, the p1d (next-session) fill is the honest one.
"""
import time
import sqlite3
import logging
from datetime import datetime, timezone

import enrich

log = logging.getLogger("paperlog")

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
  accession    TEXT PRIMARY KEY,
  ts_detected  TEXT,
  ts_filed     TEXT,
  form         TEXT,
  cik          INTEGER,
  ticker       TEXT,
  company      TEXT,
  direction    TEXT,
  conviction   INTEGER,
  reason       TEXT,
  short_factor REAL,
  flow_factor  REAL,
  score        REAL,
  alerted      INTEGER DEFAULT 0,
  ts_alert     REAL,
  price_alert  REAL,
  p5m          REAL,
  p30m         REAL,
  p1d          REAL
);
"""
FOLLOWUPS = [("p5m", 300), ("p30m", 1800), ("p1d", 86400)]


class PaperLog:
    def __init__(self, path="signals.db"):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.db.commit()

    def record(self, entry, ticker, verdict, breakdown, score, alerted, price_alert):
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """INSERT OR REPLACE INTO signals
               (accession, ts_detected, ts_filed, form, cik, ticker, company,
                direction, conviction, reason, short_factor, flow_factor, score,
                alerted, ts_alert, price_alert)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entry["accession"], now_iso, entry["filed_at"], entry["form"],
             entry["cik"], ticker, entry["title"],
             verdict["direction"], verdict["conviction"], verdict["reason"],
             breakdown.get("short"), breakdown.get("flow"), score,
             int(alerted), time.time() if alerted else None, price_alert),
        )
        self.db.commit()

    def fill_followups(self):
        """Fetch prices for alerted signals whose +5m/+30m/+1d windows are due."""
        now = time.time()
        for col, delay in FOLLOWUPS:
            rows = self.db.execute(
                f"SELECT accession, ticker FROM signals "
                f"WHERE alerted=1 AND {col} IS NULL AND ts_alert IS NOT NULL "
                f"AND ts_alert + ? <= ?", (delay, now)).fetchall()
            for accession, ticker in rows:
                price, _ = enrich.quote(ticker)
                if price is not None:
                    self.db.execute(
                        f"UPDATE signals SET {col}=? WHERE accession=?",
                        (price, accession))
                    log.info("followup %s %s %s=%.2f", accession, ticker, col, price)
            self.db.commit()

    def stats(self):
        """Quick hit-rate readout for alerted signals with a 30m fill."""
        rows = self.db.execute(
            "SELECT direction, price_alert, p30m FROM signals "
            "WHERE alerted=1 AND price_alert IS NOT NULL AND p30m IS NOT NULL").fetchall()
        if not rows:
            return "no filled alerts yet"
        hits = 0
        for direction, p0, p30 in rows:
            if p0 and ((direction == "bull" and p30 > p0) or
                       (direction == "bear" and p30 < p0)):
                hits += 1
        return f"{hits}/{len(rows)} correct at +30m ({100*hits/len(rows):.0f}%)"
