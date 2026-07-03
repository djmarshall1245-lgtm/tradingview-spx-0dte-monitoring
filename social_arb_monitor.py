import sys
import pandas as pd
from datetime import datetime
from pytrends.request import TrendReq

def run_social_arb_scan():
    print(f"[{datetime.now().isoformat()}] [SYSTEM] Launching Social Arbitrage Engine...")

    # Initialize connection to search data engine
    pytrends = TrendReq(hl='en-US', tz=360)

    # Define a high-conviction consumer tracking basket matching thematic catalysts
    # e.g., tracking clean energy spikes (Bloom Energy) or e.l.f. beauty trends
    tracking_keywords = ["Bloom Energy", "elf cosmetics", "roof repair"]

    print(f"[MONITOR] Pulling keyword trend acceleration data for: {tracking_keywords}")

    try:
        pytrends.build_payload(tracking_keywords, cat=0, timeframe='today 3-m', geo='US', gprop='')
        interest_over_time_df = pytrends.interest_over_time()

        if interest_over_time_df.empty:
            print("[WARN] Trend data payload returned empty container structures.")
            return

        print("\n=== Real-World Velocity Scorecard ===")
        for kw in tracking_keywords:
            # Calculate rolling average benchmark vs the most recent velocity points
            historical_avg = interest_over_time_df[kw].iloc[:-3].mean()
            recent_velocity = interest_over_time_df[kw].iloc[-3:].mean()

            # Formulate the Information Asymmetry Coefficient
            velocity_ratio = recent_velocity / max(historical_avg, 1)

            print(f"• Keyword: {kw:<15} | Hist Avg: {historical_avg:.1f} | Recent: {recent_velocity:.1f} | Velocity Ratio: {velocity_ratio:.2f}x")

            # Trigger Alpha Flag if recent consumer interest surges more than 1.5x above baseline
            if velocity_ratio > 1.50:
                print(f"  [🔥 SOCIAL ARB ALERT] Massive consumer divergence detected for '{kw}'!")
                print(f"  [ACTION] Initiate ground-level due diligence matrix (reviews, sentiment shifts).")

    except Exception as e:
        print(f"[ERROR] Engine timed out or met an interface block: {str(e)}")

if __name__ == "__main__":
    run_social_arb_scan()
