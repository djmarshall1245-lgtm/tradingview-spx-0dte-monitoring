#!/usr/bin/env python3
"""Trade-desk runner. The OBSERVE layer's entrypoint — reports facts, never
trades. Run on your Mac (needs network for live data).

  python run.py --brief                 # full daily monitor (macro+book+alerts+news)
  python run.py --snapshot              # just snapshot chains (daily IV-history ramp)
  python run.py --score                 # expectancy report from journal/trades.jsonl
  python run.py --shot chart            # screenshot a named region (see config.yaml)
  python run.py --shot --window         # click a window to capture
  python run.py --asof 2026-06-22 ...   # stamp a specific run date
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_yaml(name):
    import yaml
    p = ROOT / name
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def cmd_score():
    from lib import score
    score.report()


def cmd_shot(args):
    from lib import screenshot
    if args.window:
        print(screenshot.capture_window()); return
    if args.full:
        print(screenshot.capture_full()); return
    label = args.shot
    regions = (_load_yaml("config.yaml").get("screenshots", {}) or {}).get("regions", {})
    if label and label in regions:
        print(screenshot.capture_region(label, regions[label]))
    else:
        sys.exit(f"Unknown region '{label}'. Known: {', '.join(regions) or '(none)'}. "
                 f"Use --window to click-capture.")


def cmd_snapshot(asof):
    from lib import snapshot
    cfg = _load_yaml("config.yaml")
    watch = cfg.get("watchlist", [])
    res = snapshot.run(watch, [], asof=asof)
    print(f"snapshotted {len(res['snapshots'])} names as of {res['asof']}")


def cmd_brief(asof):
    cfg = _load_yaml("config.yaml")
    positions = _load_yaml("positions.yaml").get("positions", [])
    watch = cfg.get("watchlist", [])
    asof = asof or date.today().isoformat()
    print(f"=== MORNING BRIEF — {asof} (OBSERVE only, no trades) ===\n")

    # 0) overnight tells — pre-open global tape
    try:
        from lib import overnight
        print(overnight.report(cfg.get("overnight_tells")))
        print()
    except Exception as e:
        print(f"⓪ OVERNIGHT TELLS unavailable: {e}\n")

    # 1) macro
    try:
        from lib import macro_gate
        m = macro_gate.compute(cfg.get("macro_gate", {}).get("weights"))
        print(f"① MACRO {m.score}/100  regime={m.regime}  (VIX {m.vix})")
    except Exception as e:
        print(f"① MACRO unavailable: {e}")

    # 1b) IV rank via Tastytrade /market-metrics (optional — skips if no creds)
    # NB: lib module is `tasty` not `tastytrade` to avoid shadowing the SDK.
    try:
        from lib import tasty
        an = cfg.get("analytics", {})
        print()
        print(tasty.report(watch,
                           an.get("iv_rich_above", 70),
                           an.get("iv_cheap_below", 30)))
    except Exception as e:
        print(f"\nIV RANK (Tastytrade) skipped: {str(e)[:100]}")

    # 2) book health + alerts
    try:
        from lib import snapshot, alerts
        res = snapshot.run(watch, positions, asof=asof)
        a_cfg = cfg.get("alerts", {})
        fired = alerts.from_valuations(res["valuations"],
                                       a_cfg.get("target_near_pct", 80))
        print("\n② BOOK HEALTH")
        for v in res["valuations"]:
            if "error" in v:
                print(f"  {v['ticker']} {v['side']} {v['strike']}: {v['error']}")
            else:
                print(f"  {v['ticker']} {v['side']} {v['strike']} {v['expiry']}: "
                      f"mark {v['mark']} P&L {v['unreal_pnl_pct']}% DTE {v['dte']} "
                      f"theta/day ${v['theta_day']} IVrank {v['iv_rank']}({v['iv_label']}) "
                      f"->tgt {v['progress_to_target_pct']}%")
        print("\n③ CONDITION ALERTS")
        for al in fired or [{"message": "none"}]:
            print(f"  [{al.get('severity','-')}] {al['message']}")
    except Exception as e:
        print(f"② BOOK / ③ ALERTS unavailable: {e}")

    # 4) per-name headlines (raw — Claude Code summarizes via Firecrawl/UW MCP)
    try:
        from lib import news
        n_cfg = cfg.get("news", {})
        names = (positions and [p["ticker"] for p in positions]) or watch
        print("\n④ HEADLINES (raw — paste into Claude Code w/ morning_brief.md "
              "to get Firecrawl-enriched summaries)")
        for t in names:
            hs = news.headlines(t, n_cfg.get("window_days", 3))
            print(f"  {t}: {len(hs)} headlines")
            for h in hs[:3]:
                print(f"    - {h['title']} ({h['publisher']})")
    except Exception as e:
        print(f"④ HEADLINES unavailable: {e}")

    print("\n⑤ No trade calls here. Take a setup to the trade desk — you are the GO.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--shot", nargs="?", const="", help="named region, or use --window/--full")
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--asof", default=None)
    args = ap.parse_args()

    ran = False
    if args.shot is not None or args.window or args.full:
        cmd_shot(args); ran = True
    if args.snapshot:
        cmd_snapshot(args.asof); ran = True
    if args.score:
        cmd_score(); ran = True
    if args.brief:
        cmd_brief(args.asof); ran = True
    if not ran:
        ap.print_help()


if __name__ == "__main__":
    main()
