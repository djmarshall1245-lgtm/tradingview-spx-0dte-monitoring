#!/usr/bin/env python3
"""
uw_dashboard.py — Unusual Whales flow/dark-pool/earnings dashboard + ntfy push.

MANUAL TRIGGER ONLY (LaunchAgents post-mortem applies: never schedule this).
Each run: pull → render HTML → open in browser → push ntfy notifications for
NEW items above the notify thresholds (deduped via a local state file).
Optional --watch N keeps polling every N seconds in the FOREGROUND while you
sit at the desk (Ctrl-C to stop). It burns zero LLM tokens — pure API pulls —
but it still ends when you leave: do not wrap it in a scheduler.

SECTIONS
  ① FLOW ALERTS  — sweeps above --flow-min premium (default $250k)
  ② DARK POOL    — block prints above --dp-min premium (default $5M)
  ③ EARNINGS     — today AMC + next-trading-day BMO reporters, each with
                   IV rank + options volume / put-call read

SETUP (~/.zshrc — never in this repo):
  export UW_API_TOKEN="..."        # unusualwhales.com API token
  export NTFY_TOPIC="..."          # your ntfy topic (secret — pick something unguessable)
  export NTFY_SERVER="https://ntfy.sh"   # optional, this is the default

USAGE
  python3 uw_dashboard.py                    # one shot: pull, render, notify, exit
  python3 uw_dashboard.py --watch 120        # re-pull every 120s until Ctrl-C
  python3 uw_dashboard.py --flow-min 500000 --dp-min 10000000
  python3 uw_dashboard.py --tickers SPY,QQQ,TSLA   # flow section filter
  python3 uw_dashboard.py --no-notify --no-open

OUTPUT: data/uw_dashboard.html (gitignored) + ntfy pushes.
State:  data/uw_dashboard_state.json (gitignored) — IDs already notified.

HONESTY NOTE: endpoints follow the documented UW API (Bearer auth,
api.unusualwhales.com). Any section that errors renders a loud red box with
the HTTP status/body instead of silently showing partial data.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE = "https://api.unusualwhales.com"
REPO = Path(__file__).resolve().parent
OUT_HTML = REPO / "data" / "uw_dashboard.html"
STATE_FILE = REPO / "data" / "uw_dashboard_state.json"

# ---------------------------------------------------------------- http helpers

def api_get(path, token, params=None):
    """GET a UW endpoint. Returns (data, error_string). Never raises."""
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "uw-dashboard/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
            return body, None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]
        except Exception:
            pass
        return None, f"HTTP {e.code} on {path} — {detail or e.reason}"
    except Exception as e:
        return None, f"{type(e).__name__} on {path}: {e}"


def rows_of(body):
    """UW responses wrap lists as {'data': [...]} — unwrap defensively."""
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        d = body.get("data")
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            return [d]
    return []


def g(d, *keys, default=None):
    """First present, non-None key."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def money(x):
    x = fnum(x)
    if x >= 1e9:
        return f"${x/1e9:.2f}B"
    if x >= 1e6:
        return f"${x/1e6:.2f}M"
    if x >= 1e3:
        return f"${x/1e3:.0f}k"
    return f"${x:.0f}"

# ------------------------------------------------------------------- sections

def fetch_flow(token, min_prem, tickers):
    params = {"limit": 200, "min_premium": int(min_prem)}
    body, err = api_get("/api/option-trades/flow-alerts", token, params)
    if err:
        return [], err
    out = []
    for a in rows_of(body):
        prem = fnum(g(a, "total_premium", "premium"))
        if prem < min_prem:
            continue
        tick = str(g(a, "ticker", "ticker_symbol", "underlying_symbol", default="?")).upper()
        if tickers and tick not in tickers:
            continue
        rule = str(g(a, "alert_rule", "rule_name", "rule_id", default=""))
        sweep = bool(g(a, "has_sweep", "is_sweep", default=False)) or "sweep" in rule.lower()
        out.append({
            "id": str(g(a, "id", default="")) or hashlib.sha1(
                f"{tick}{g(a,'strike')}{g(a,'expiry')}{g(a,'created_at')}{prem}".encode()).hexdigest()[:16],
            "time": str(g(a, "created_at", "executed_at", "tape_time", default="")),
            "ticker": tick,
            "cp": str(g(a, "type", "option_type", default="?")).upper()[:4],
            "strike": g(a, "strike", default="?"),
            "expiry": str(g(a, "expiry", "expires", default="?")),
            "premium": prem,
            "size": g(a, "total_size", "size", "volume", default=""),
            "rule": rule,
            "sweep": sweep,
            "ask_prem": fnum(g(a, "total_ask_side_prem", "ask_side_premium")),
            "bid_prem": fnum(g(a, "total_bid_side_prem", "bid_side_premium")),
            "otm": g(a, "otm", "is_otm", default=""),
            "spot": g(a, "underlying_price", default=""),
        })
    out.sort(key=lambda r: r["premium"], reverse=True)
    return out, None


def fetch_darkpool(token, min_prem):
    body, err = api_get("/api/darkpool/recent", token, {"limit": 200})
    if err:
        return [], err
    out = []
    for p in rows_of(body):
        price = fnum(g(p, "price"))
        size = fnum(g(p, "size", "volume"))
        prem = fnum(g(p, "premium")) or price * size
        if prem < min_prem:
            continue
        tick = str(g(p, "ticker", "ticker_symbol", default="?")).upper()
        out.append({
            "id": str(g(p, "tracking_id", "id", default="")) or hashlib.sha1(
                f"{tick}{g(p,'executed_at')}{size}{price}".encode()).hexdigest()[:16],
            "time": str(g(p, "executed_at", "created_at", default="")),
            "ticker": tick,
            "price": price,
            "size": size,
            "premium": prem,
            "nbbo_bid": g(p, "nbbo_bid", default=""),
            "nbbo_ask": g(p, "nbbo_ask", default=""),
        })
    out.sort(key=lambda r: r["premium"], reverse=True)
    return out, None


# A put/call ratio computed on a handful of contracts is noise, not signal
# (WTFC printed 13.0 on 14 total contracts on 2026-07-20). Below this total
# option volume the ratio is suppressed to [thin].
MIN_OPT_VOL_FOR_RATIO = 500


def next_trading_day(d):
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:  # Sat/Sun; holidays not handled — noted on dashboard
        nd += timedelta(days=1)
    return nd


def debug_earn(token, ticker):
    """One-shot schema probe: dump the raw iv-rank + options-volume JSON for
    ONE ticker so the IV-rank field can be mapped exactly (it renders '?'
    because the field name isn't yet known). Run on a machine that reaches UW."""
    t = ticker.upper()
    for path in (f"/api/stock/{t}/iv-rank",
                 f"/api/stock/{t}/volatility/stats",
                 f"/api/stock/{t}/options-volume"):
        body, err = api_get(path, token, {"limit": 1})
        print(f"\n=== {path} ===")
        print(f"ERROR: {err}" if err else json.dumps(body, indent=2)[:1500])


def fetch_earnings(token, max_names):
    today = datetime.now(ET).date()
    nxt = next_trading_day(today)
    reporters, errs = [], []
    for path, params, label in (
        ("/api/earnings/afterhours", {"date": today.isoformat(), "limit": 50}, f"AMC {today.isoformat()}"),
        ("/api/earnings/premarket", {"date": nxt.isoformat(), "limit": 50}, f"BMO {nxt.isoformat()}"),
    ):
        body, err = api_get(path, token, params)
        if err:
            errs.append(err)
            continue
        for e in rows_of(body):
            tick = str(g(e, "symbol", "ticker", default="")).upper()
            if tick:
                reporters.append({"ticker": tick, "when": label,
                                  "sector": g(e, "sector", default="")})
    # de-dup, cap request fan-out
    seen, capped = set(), []
    for r in reporters:
        if r["ticker"] not in seen:
            seen.add(r["ticker"])
            capped.append(r)
    capped = capped[:max_names]
    # enrich: IV rank + options volume (2 requests per name)
    for r in capped:
        t = r["ticker"]
        iv_body, iv_err = api_get(f"/api/stock/{t}/iv-rank", token, {"limit": 1})
        if iv_err:  # fallback endpoint name
            iv_body, iv_err = api_get(f"/api/stock/{t}/volatility/stats", token)
        iv_rows = rows_of(iv_body)
        # broadened field candidates — the exact one is confirmed via
        # `python3 uw_dashboard.py --debug-earn TICKER` (dumps raw JSON).
        r["iv_rank"] = g(iv_rows[0], "iv_rank", "iv_rank_30d", "iv_rank_current",
                         "iv_percentile", "ivr", "rank", default="?") if iv_rows else "?"
        ov_body, ov_err = api_get(f"/api/stock/{t}/options-volume", token, {"limit": 1})
        ov = rows_of(ov_body)
        if ov:
            cp, pp = fnum(g(ov[0], "call_premium")), fnum(g(ov[0], "put_premium"))
            cv, pv = fnum(g(ov[0], "call_volume")), fnum(g(ov[0], "put_volume"))
            r["call_prem"], r["put_prem"] = cp, pp
            r["opt_vol"] = int(cv + pv)
            # thin-tape guard: a P/C ratio on a handful of contracts is noise
            # (WTFC 13.0 on 14 contracts on 2026-07-20). Only show it when the
            # chain has real participation.
            r["pc_ratio"] = round(pv / cv, 2) if (cv and r["opt_vol"] >= MIN_OPT_VOL_FOR_RATIO) else "[thin]"
        else:
            r["call_prem"] = r["put_prem"] = 0
            r["pc_ratio"] = "[thin]"
            r["opt_vol"] = 0
        r["err"] = "; ".join(x for x in (iv_err, ov_err) if x) or ""
    # meaningful names (real options interest) first; dead 0-volume rows sink
    capped.sort(key=lambda r: r.get("opt_vol") or 0, reverse=True)
    return capped, ("; ".join(errs) or None)

# ----------------------------------------------------------------------- ntfy

def ntfy_push(title, message, tags):
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return "NTFY_TOPIC not set"
    req = urllib.request.Request(
        f"{server}/{topic}", data=message.encode(),
        headers={"Title": title, "Tags": tags, "Priority": "default"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            return None
    except Exception as e:
        return f"ntfy failed: {e}"


def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text()).get("notified", []))
    except Exception:
        return set()


def save_state(ids):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"notified": list(ids)[-5000:]}))


def notify_new(flow, dp, notify_flow_min, notify_dp_min, sweeps_only=True):
    """Push ntfy for NEW items above notify thresholds. Returns (count, err).
    sweeps_only: pro triage — the table shows all flow, the phone only rings
    for sweeps (multi-exchange aggression). --notify-all-flow disables it."""
    seen = load_state()
    sent, err = 0, None
    for a in flow:
        if sweeps_only and not a["sweep"]:
            continue
        if a["premium"] >= notify_flow_min and a["id"] not in seen:
            side = "ask-lean" if a["ask_prem"] > a["bid_prem"] else "bid-lean" if a["bid_prem"] > a["ask_prem"] else ""
            e = ntfy_push(
                f"UW FLOW {a['ticker']} {money(a['premium'])}",
                f"{a['ticker']} {a['strike']}{a['cp'][:1]} exp {a['expiry']} · "
                f"{money(a['premium'])} {'SWEEP' if a['sweep'] else a['rule']} {side}".strip(),
                "whale,chart_with_upwards_trend")
            if e:
                err = e
                break
            seen.add(a["id"]); sent += 1
    for p in dp:
        if p["premium"] >= notify_dp_min and p["id"] not in seen:
            e = ntfy_push(
                f"UW DARK POOL {p['ticker']} {money(p['premium'])}",
                f"{p['ticker']} {int(p['size']):,} shares @ {p['price']:.2f} = {money(p['premium'])}",
                "new_moon,bank")
            if e:
                err = e
                break
            seen.add(p["id"]); sent += 1
    save_state(seen)
    return sent, err

# ----------------------------------------------------------------------- html

CSS = """
body{background:#0d1117;color:#e6edf3;font:14px -apple-system,Segoe UI,sans-serif;margin:0;padding:20px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 8px;color:#79c0ff}
.meta{color:#8b949e;font-size:12px;margin-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:13px}
th{color:#8b949e;text-align:left;padding:5px 10px 5px 0;border-bottom:1px solid #30363d;font-weight:600}
td{padding:5px 10px 5px 0;border-bottom:1px solid #21262d;white-space:nowrap}
.call{color:#3fb950}.put{color:#f85149}.sweep{color:#d29922;font-weight:700}
.err{background:#3d1d1f;border:1px solid #f85149;color:#ffa198;padding:10px;border-radius:6px;margin:8px 0;font-family:monospace;font-size:12px}
.pill{background:#21262d;border-radius:10px;padding:1px 8px;font-size:11px;color:#8b949e;margin-left:6px}
"""

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def t_et(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET).strftime("%H:%M:%S")
    except Exception:
        return esc(iso)[:19]


def render(flow, flow_err, dp, dp_err, earn, earn_err, args, notified):
    now = datetime.now(ET)
    h = [f"<html><head><meta charset='utf-8'><title>UW Dashboard</title><style>{CSS}</style></head><body>"]
    h.append(f"<h1>🐋 Unusual Whales Dashboard</h1><div class='meta'>Pulled {now.strftime('%A %Y-%m-%d %H:%M:%S')} ET"
             f" · all rows [TOOL] live this pull · ntfy sent this run: {notified}</div>")

    notify_scope = "all flow" if args.notify_all_flow else "SWEEPS only"
    h.append(f"<h2>① FLOW ALERTS — ≥ {money(args.flow_min)}"
             f"<span class='pill'>notify: {notify_scope} ≥ {money(args.notify_flow_min)}</span></h2>")
    if flow_err:
        h.append(f"<div class='err'>FLOW SECTION FAILED — no data shown (not partial): {esc(flow_err)}</div>")
    elif not flow:
        h.append("<div class='meta'>No alerts above threshold this pull.</div>")
    else:
        h.append("<table><tr><th>ET</th><th>Ticker</th><th>C/P</th><th>Strike</th><th>Expiry</th>"
                 "<th>Premium</th><th>Size</th><th>Rule</th><th>Ask/Bid prem</th><th>Spot</th></tr>")
        for a in flow[:60]:
            cls = "call" if a["cp"].startswith("C") else "put"
            rule = f"<span class='sweep'>SWEEP</span> {esc(a['rule'])}" if a["sweep"] else esc(a["rule"])
            h.append(f"<tr><td>{t_et(a['time'])}</td><td><b>{esc(a['ticker'])}</b></td>"
                     f"<td class='{cls}'>{esc(a['cp'])}</td><td>{esc(a['strike'])}</td><td>{esc(a['expiry'])}</td>"
                     f"<td><b>{money(a['premium'])}</b></td><td>{esc(a['size'])}</td><td>{rule}</td>"
                     f"<td>{money(a['ask_prem'])} / {money(a['bid_prem'])}</td><td>{esc(a['spot'])}</td></tr>")
        h.append("</table>")

    h.append(f"<h2>② DARK POOL — prints ≥ {money(args.dp_min)}"
             f"<span class='pill'>notify ≥ {money(args.notify_dp_min)}</span></h2>")
    if dp_err:
        h.append(f"<div class='err'>DARK POOL SECTION FAILED — no data shown (not partial): {esc(dp_err)}</div>")
    elif not dp:
        h.append("<div class='meta'>No prints above threshold this pull.</div>")
    else:
        h.append("<table><tr><th>ET</th><th>Ticker</th><th>Size</th><th>Price</th><th>Premium</th><th>NBBO bid/ask</th></tr>")
        for p in dp[:40]:
            h.append(f"<tr><td>{t_et(p['time'])}</td><td><b>{esc(p['ticker'])}</b></td>"
                     f"<td>{int(p['size']):,}</td><td>{p['price']:.2f}</td><td><b>{money(p['premium'])}</b></td>"
                     f"<td>{esc(p['nbbo_bid'])} / {esc(p['nbbo_ask'])}</td></tr>")
        h.append("</table>")

    h.append("<h2>③ EARNINGS — today AMC + next-trading-day BMO "
             "<span class='pill'>sorted by volume · P/C hidden below "
             f"{MIN_OPT_VOL_FOR_RATIO} contracts · holidays not skipped</span></h2>")
    if earn_err:
        h.append(f"<div class='err'>EARNINGS PULL PARTIAL/FAILED: {esc(earn_err)}</div>")
    if earn:
        h.append("<table><tr><th>Ticker</th><th>Reports</th><th>IV rank</th><th>Opt volume</th>"
                 "<th>P/C ratio</th><th>Call prem</th><th>Put prem</th><th>Sector</th></tr>")
        for r in earn:
            note = f" <span class='pill'>{esc(r['err'])}</span>" if r.get("err") else ""
            ov = r.get("opt_vol") or 0
            pc = r["pc_ratio"]
            pc_cell = f"<span class='meta'>{esc(pc)}</span>" if pc == "[thin]" else esc(pc)
            h.append(f"<tr><td><b>{esc(r['ticker'])}</b>{note}</td><td>{esc(r['when'])}</td>"
                     f"<td>{esc(r['iv_rank'])}</td><td>{ov:,}</td><td>{pc_cell}</td>"
                     f"<td>{money(r['call_prem'])}</td><td>{money(r['put_prem'])}</td><td>{esc(r['sector'])}</td></tr>")
        h.append("</table>")
        if any(r["iv_rank"] == "?" for r in earn):
            h.append("<div class='meta'>IV rank shows ? — UW field name not yet mapped. "
                     "Run <code>python3 uw_dashboard.py --debug-earn AGNC</code> and share the output to fix it.</div>")
    elif not earn_err:
        h.append("<div class='meta'>No reporters found for the window.</div>")

    h.append("<div class='meta' style='margin-top:20px'>Manual runs only — never schedule (LaunchAgents post-mortem). "
             "Advisory data layer: this gates nothing and places nothing.</div></body></html>")
    return "".join(h)

# ----------------------------------------------------------------------- main

def run_once(args, token, opened):
    tickers = {t.strip().upper() for t in args.tickers.split(",") if t.strip()} if args.tickers else None
    flow, flow_err = fetch_flow(token, args.flow_min, tickers)
    dp, dp_err = fetch_darkpool(token, args.dp_min)
    earn, earn_err = ([], None) if args.no_earnings else fetch_earnings(token, args.earnings_max)

    notified, ntfy_err = (0, None)
    if not args.no_notify:
        notified, ntfy_err = notify_new(flow, dp, args.notify_flow_min, args.notify_dp_min,
                                        sweeps_only=not args.notify_all_flow)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(render(flow, flow_err, dp, dp_err, earn, earn_err, args, notified))

    now = datetime.now(ET).strftime("%H:%M:%S")
    print(f"[{now} ET] flow={len(flow)}{' ERR' if flow_err else ''} "
          f"darkpool={len(dp)}{' ERR' if dp_err else ''} earnings={len(earn)} "
          f"ntfy_sent={notified}{' NTFY_ERR:' + ntfy_err if ntfy_err else ''} → {OUT_HTML}")
    for e in (flow_err, dp_err, earn_err):
        if e:
            print(f"  !! {e}", file=sys.stderr)
    if not args.no_open and not opened:
        webbrowser.open(OUT_HTML.as_uri())
        return True
    return opened


def main():
    ap = argparse.ArgumentParser(description="UW dashboard + ntfy (manual trigger only)")
    ap.add_argument("--flow-min", type=float, default=250_000, help="flow section min premium (default 250k)")
    ap.add_argument("--dp-min", type=float, default=5_000_000, help="dark pool section min premium (default 5M)")
    ap.add_argument("--notify-flow-min", type=float, default=1_000_000, help="ntfy threshold for flow (default 1M)")
    ap.add_argument("--notify-dp-min", type=float, default=20_000_000, help="ntfy threshold for dark pool (default 20M)")
    ap.add_argument("--tickers", default="", help="comma list to filter flow alerts (default: whole market)")
    ap.add_argument("--earnings-max", type=int, default=12, help="max earnings names to enrich (default 12)")
    ap.add_argument("--notify-all-flow", action="store_true",
                    help="notify on ALL flow >= threshold, not just sweeps (default: sweeps only)")
    ap.add_argument("--no-earnings", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="foreground re-pull loop (min 60s, Ctrl-C to stop). NOT a scheduler.")
    ap.add_argument("--debug-earn", metavar="TICKER", default="",
                    help="dump raw UW iv-rank/options-volume JSON for one ticker, then exit")
    args = ap.parse_args()

    token = os.environ.get("UW_API_TOKEN", "")
    if not token:
        sys.exit("UW_API_TOKEN not set. Add to ~/.zshrc:  export UW_API_TOKEN=\"...\"  (never in the repo)")
    if args.debug_earn:
        debug_earn(token, args.debug_earn)
        return
    if not os.environ.get("NTFY_TOPIC") and not args.no_notify:
        print("NOTE: NTFY_TOPIC not set — running without notifications (dashboard only).")
        args.no_notify = True

    opened = run_once(args, token, opened=False)
    if args.watch:
        interval = max(60, args.watch)
        print(f"Watching every {interval}s — foreground only, Ctrl-C to stop.")
        try:
            while True:
                time.sleep(interval)
                opened = run_once(args, token, opened)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
