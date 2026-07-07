#!/usr/bin/env python3
"""edgar-synth: EDGAR watcher -> LLM triage -> synthesis score -> alert + paper log.

Usage:
    python3 run.py              # main loop (6am-10pm ET weekdays)
    python3 run.py --stats      # print paper-log hit rate and exit
    python3 run.py --once       # single poll cycle (debug)

No execution anywhere in this system. Alerts + paper log only.
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

import edgar
import triage
import enrich
import synthesis
import alerts
import paperlog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler("edgar_synth.log")],
)
log = logging.getLogger("run")


def in_window(cfg):
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    hhmm = now.strftime("%H:%M")
    return cfg["window_start"] <= hhmm <= cfg["window_end"]


def heartbeat(path):
    Path(path).touch()


def process_entry(cfg, watcher, uw, plog, universe, cik_map, entry):
    ticker = cik_map.get(entry["cik"])
    if not ticker or ticker not in universe:
        return
    log.info("HIT %s %s %s", entry["form"], ticker, entry["accession"])

    # Phase 2: triage
    doc = watcher.fetch_primary_text(entry, cfg["llm"]["max_doc_chars"])
    verdict = triage.classify(cfg["llm"], entry, ticker, doc)
    log.info("verdict %s %s conv=%d %s", ticker, verdict["direction"],
             verdict["conviction"], verdict["reason"][:120])

    # Phase 3: enrich + synthesize only if worth the API calls
    breakdown, comp_score = {"short": 0.0, "flow": 0.0}, 0.0
    if verdict["conviction"] >= cfg["min_conviction_for_enrich"]:
        short = uw.short_data(ticker)
        flow = uw.flow_summary(ticker)
        comp_score, breakdown = synthesis.score(cfg["synthesis"], verdict, short, flow)
        log.info("score %s %.1f %s", ticker, comp_score, breakdown)

    # Phase 4: alert + log
    alerted = (comp_score >= cfg["alert_score_min"]
               and verdict["conviction"] >= cfg["alert_conviction_min"])
    price = None
    if alerted:
        price, _ = enrich.quote(ticker)
        alerts.send(cfg["alerts"], ticker, entry, verdict, comp_score, price)
    plog.record(entry, ticker, verdict, breakdown, comp_score, alerted, price)


def main():
    cfg = yaml.safe_load(Path("config.yaml").read_text())

    if "--stats" in sys.argv:
        print(paperlog.PaperLog(cfg["db_path"]).stats())
        return

    watcher = edgar.EdgarWatcher(cfg["sec_user_agent"], cfg["target_forms"],
                                 cfg["feed_count"],
                                 cfg.get("feed_timeout_sec", 30))
    universe = enrich.load_universe(cfg)
    cik_map = watcher.load_cik_map()
    uw = enrich.UWClient()
    plog = paperlog.PaperLog(cfg["db_path"])
    log.info("started: universe=%d ciks=%d forms=%s",
             len(universe), len(cik_map), cfg["target_forms"])

    once = "--once" in sys.argv
    universe_check = time.time()
    while True:
        heartbeat(cfg["heartbeat_path"])
        try:
            if not in_window(cfg) and not once:
                time.sleep(60)
                continue
            for entry in watcher.poll():
                if watcher.is_target(entry):
                    process_entry(cfg, watcher, uw, plog, universe, cik_map, entry)
            plog.fill_followups()
            if time.time() - universe_check > 3600:      # hourly staleness check
                universe = enrich.load_universe(cfg)     # no-op unless cache expired
                universe_check = time.time()
        except KeyboardInterrupt:
            log.info("stopped by user")
            break
        except Exception as e:  # noqa: BLE001 - loop must survive anything
            log.error("loop error: %s", e, exc_info=True)
            time.sleep(10)
        if once:
            break
        time.sleep(cfg["poll_interval_sec"])


if __name__ == "__main__":
    main()
