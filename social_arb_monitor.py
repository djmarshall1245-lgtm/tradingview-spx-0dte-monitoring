import json
import os
import sys
import time
import urllib.request
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from pytrends.request import TrendReq

# Consumer-INTENT keywords (what buyers type, not tickers) -> mapped ticker.
# pytrends caps 5 keywords per payload; keywords are normalized 0-100 within
# a batch, so group similar-magnitude terms together. Velocity ratio is
# per-keyword vs its own history, so cross-batch comparison is safe.
KEYWORD_BATCHES = [
    # Batch 1: mega-volume consumer terms
    {
        "Ozempic": "LLY/NVO (inverse: PEP/MDLZ snacks)",
        "Roblox codes": "RBLX",
        "Temu": "PDD (inverse: AMZN low-end, DLTR)",
        "Crocs": "CROX",
        "DraftKings promo": "DKNG",
    },
    # Batch 2: large-volume product/brand terms
    {
        "roof repair": "BECN",
        "Zepbound": "LLY",
        "Celsius energy drink": "CELH",
        "Birkenstock": "BIRK",
        "Stanley tumbler": "private (proxy: retail sellers TSCO/DKS)",
    },
    # Batch 3: mid-volume brand/engagement terms
    {
        "home battery backup": "GNRC/BE",
        "e.l.f. lip oil": "ELF",
        "Duolingo": "DUOL",
        "Cava restaurant": "CAVA",
        "On Cloud shoes": "ONON",
    },
    # Batch 4: intent / problem searches (lower volume, highest signal)
    {
        "whole house generator": "GNRC",
        "mounjaro side effects": "LLY (adoption-curve read)",
        "sell on TikTok Shop": "merchant adoption (inverse: ETSY/AMZN 3P)",
        "solar panel installation": "ENPH/RUN/FSLR",
        "Abercrombie": "ANF",
    },
    # Batch 5: durable macro themes via consumer-intent phrasing
    {
        "electric bill too high": "VST/CEG/NRG (grid tightness, real-economy)",
        "nuclear energy": "CCJ/SMR/OKLO (theme attention gauge)",  # swapped from "nuclear energy stocks" 2026-07-17 — 2.9 hist avg fell under the [NOISE] floor; broad term has a real base
        "car insurance too expensive": "PGR/ALL (pricing-power signal)",
        "humanoid robot": "TSLA/robot supply chain (attention gauge)",
        "clothes too big": "GLP-1 2nd-order: apparel refresh, BRBR",
    },
    # Batch 6: AI / quantum / data-center intent terms
    {
        "ChatGPT plus": "MSFT/NVDA proxy (paid-usage velocity)",
        "Nvidia stock": "NVDA retail FOMO gauge (contrarian at extremes)",
        "quantum computing stocks": "IONQ/RGTI/QBTS (retail wave detector)",
        "data center construction": "VRT/ETN/PWR (build-out demand)",
        "GPU price": "NVDA/AMD (consumer demand)",
    },
]

VELOCITY_ALERT_THRESHOLD = 1.50

# Terms whose historical average sits below this floor produce meaningless
# ratios (one index point of movement = a huge fake velocity swing, e.g.
# Celsius 2.8→1.0 printing "0.35x" on 2026-07-17). Those rows print with a
# [NOISE] tag and are excluded from firing alerts.
MIN_HIST_AVG = 5.0

# ntfy push on 🔥 alerts — same NTFY_TOPIC env var as uw_dashboard.py
# (~/.zshrc, never in repo). Unset topic = terminal-only, no error.
# Dedupe: one push per (keyword, day) via state file, so re-running the
# scan the same day doesn't re-ping the phone.
NTFY_STATE = Path(__file__).resolve().parent / "data" / "social_arb_ntfy_state.json"


def _ntfy_alert(kw, mapping, ratio):
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    key = f"{date.today().isoformat()}:{kw}"
    try:
        seen = json.loads(NTFY_STATE.read_text()).get("sent", [])
    except Exception:
        seen = []
    if key in seen:
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    req = urllib.request.Request(
        f"{server}/{topic}",
        data=f"'{kw}' searches at {ratio:.2f}x baseline → {mapping}. Ground-truth before any position.".encode(),
        headers={"Title": f"SOCIAL ARB {kw} {ratio:.2f}x", "Tags": "fire,chart_with_upwards_trend"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
        NTFY_STATE.parent.mkdir(parents=True, exist_ok=True)
        NTFY_STATE.write_text(json.dumps({"sent": (seen + [key])[-500:]}))
    except Exception as e:
        print(f"  [WARN] ntfy push failed: {e}")

# Backoff tuning: Google 429s aggressively on back-to-back payloads.
INTER_BATCH_SLEEP = 60          # seconds between successful batches
MAX_RETRIES = 3                 # retries per batch on failure
BACKOFF_BASE = 90               # 429 backoff: 90s, 180s, 360s


def scan_batch(pytrends, keyword_map):
    keywords = list(keyword_map.keys())
    print(f"[MONITOR] Pulling trend data for batch: {keywords}")

    pytrends.build_payload(keywords, cat=0, timeframe='today 3-m', geo='US', gprop='')
    df = pytrends.interest_over_time()

    if df.empty:
        print("[WARN] Trend data payload returned empty container structures.")
        return

    for kw in keywords:
        # Rolling baseline vs the most recent velocity points (~3 weeks)
        historical_avg = df[kw].iloc[:-3].mean()
        recent_velocity = df[kw].iloc[-3:].mean()

        velocity_ratio = recent_velocity / max(historical_avg, 1)

        if historical_avg < MIN_HIST_AVG:
            print(f"• {kw:<20} -> {keyword_map[kw]:<38} | Hist Avg: {historical_avg:.1f} | Recent: {recent_velocity:.1f} | [NOISE] base <{MIN_HIST_AVG:.0f} — ratio not meaningful")
            continue

        print(f"• {kw:<20} -> {keyword_map[kw]:<38} | Hist Avg: {historical_avg:.1f} | Recent: {recent_velocity:.1f} | Velocity: {velocity_ratio:.2f}x")

        if velocity_ratio > VELOCITY_ALERT_THRESHOLD:
            print(f"  [🔥 SOCIAL ARB ALERT] Consumer divergence on '{kw}' (maps to {keyword_map[kw]})")
            print(f"  [ACTION] Ground-truth it: crawl reviews/reddit sentiment before any position.")
            _ntfy_alert(kw, keyword_map[kw], velocity_ratio)


def run_social_arb_scan():
    print(f"[{datetime.now().isoformat()}] [SYSTEM] Launching Social Arbitrage Engine...")

    pytrends = TrendReq(hl='en-US', tz=360)

    print("\n=== Real-World Velocity Scorecard ===")
    for i, batch in enumerate(KEYWORD_BATCHES):
        if len(batch) > 5:
            print(f"[ERROR] Batch {i + 1} has {len(batch)} keywords; pytrends max is 5. Skipping.")
            continue
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                scan_batch(pytrends, batch)
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    print(f"[ERROR] Batch {i + 1} failed after {MAX_RETRIES} attempts: {str(e)}")
                else:
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    print(f"[WARN] Batch {i + 1} attempt {attempt} failed ({str(e)}). Backing off {wait}s...")
                    time.sleep(wait)
        if i < len(KEYWORD_BATCHES) - 1:
            print(f"[SYSTEM] Sleeping {INTER_BATCH_SLEEP}s before next batch...")
            time.sleep(INTER_BATCH_SLEEP)


if __name__ == "__main__":
    run_social_arb_scan()
