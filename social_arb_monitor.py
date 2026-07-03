import sys
import time
import pandas as pd
from datetime import datetime
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
]

VELOCITY_ALERT_THRESHOLD = 1.50


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

        print(f"• {kw:<20} -> {keyword_map[kw]:<38} | Hist Avg: {historical_avg:.1f} | Recent: {recent_velocity:.1f} | Velocity: {velocity_ratio:.2f}x")

        if velocity_ratio > VELOCITY_ALERT_THRESHOLD:
            print(f"  [🔥 SOCIAL ARB ALERT] Consumer divergence on '{kw}' (maps to {keyword_map[kw]})")
            print(f"  [ACTION] Ground-truth it: crawl reviews/reddit sentiment before any position.")


def run_social_arb_scan():
    print(f"[{datetime.now().isoformat()}] [SYSTEM] Launching Social Arbitrage Engine...")

    pytrends = TrendReq(hl='en-US', tz=360)

    print("\n=== Real-World Velocity Scorecard ===")
    for i, batch in enumerate(KEYWORD_BATCHES):
        if len(batch) > 5:
            print(f"[ERROR] Batch {i + 1} has {len(batch)} keywords; pytrends max is 5. Skipping.")
            continue
        try:
            scan_batch(pytrends, batch)
        except Exception as e:
            print(f"[ERROR] Batch {i + 1} failed (likely Google 429 rate-limit): {str(e)}")
        if i < len(KEYWORD_BATCHES) - 1:
            time.sleep(5)  # pause between payloads to dodge rate-limiting


if __name__ == "__main__":
    run_social_arb_scan()
