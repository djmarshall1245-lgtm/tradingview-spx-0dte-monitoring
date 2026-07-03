import os
import sys
import json
from datetime import datetime, timedelta

TARGET_ACCOUNT = "3232"
TARGET_INDEX = "SPY"
ALLOCATION_SIZE = 0.20   # Maximum 20% premium allocation per options trade

def preflight_check():
    print(f"[{datetime.now().isoformat()}] [SYSTEM] Initializing Robinhood Options Engine...")
    print(f"[SYSTEM] Account: ••••{TARGET_ACCOUNT} | Instrument: {TARGET_INDEX} Options")

# ==========================================
# OPTIONS STRATEGY ENGINE
# ==========================================
def evaluate_options_strategy(spot_price, vwap, ema_5, ema_13, ema_21, net_gex, vold_trend, add_value):
    """
    Wall Street Framework: Identifies if the microstructure requires
    buying a Call Option, buying a Put Option, or staying in Cash.
    """
    # 1. Institutional Flow Checks
    gamma_is_positive = net_gex > 0
    bullish_volume = vold_trend > 0 and add_value > 500
    bearish_volume = vold_trend < 0 and add_value < -500

    # 2. Price Geometry Checks
    price_above_vwap = spot_price > vwap
    emas_bullish = ema_5 > ema_13 > ema_21
    emas_bearish = ema_5 < ema_13 < ema_21

    print("\n=== Live Options Strategy Audit ===")
    print(f"• Spot Price: ${spot_price} | VWAP: ${vwap}")
    print(f"• Net GEX Status: {'Positive' if gamma_is_positive else 'Negative'} ({net_gex})")
    print(f"• Market Internals: VOLD={vold_trend} | ADD={add_value}")

    # CALL OPTION TRIGGER: Price breaking up, supported by positive GEX stability and buy volume
    if gamma_is_positive and price_above_vwap and emas_bullish and bullish_volume:
        return "BUY_CALL"

    # PUT OPTION TRIGGER: Price collapsing below VWAP, breaking short gamma floors, and heavy distribution volume
    elif not gamma_is_positive and not price_above_vwap and emas_bearish and bearish_volume:
        return "BUY_PUT"

    return "NEUTRAL"

# ==========================================
# OPTION CHAIN STRIKE & EXPIRATION SELECTOR
# ==========================================
def generate_options_ticket(signal, current_price, option_bid, option_ask,
                            trade_style="0DTE", chain_expiration=None):
    """
    Selects the right contract parameters.
    - '0DTE': Targets same-day expiration for rapid intraday delta scaling.
    - 'SWING': Targets 7 to 14 days out to protect against immediate theta decay.
    chain_expiration: expiry string from get_option_chains (live mode).
    Overrides the calendar engine — the chain is holiday-aware, the calendar is not.
    """
    if signal == "NEUTRAL":
        return None

    if chain_expiration:
        expiration_str = chain_expiration
    else:
        current_time = datetime.now()

        # Dynamic Expiration Engine (Skips weekends automatically — NOT holidays;
        # live mode must pass chain_expiration from get_option_chains)
        if trade_style == "0DTE":
            # Handle Friday/Weekend execution context safely for Monday delivery
            if current_time.weekday() == 4:   # Friday
                exp_date = current_time + timedelta(days=3)
            elif current_time.weekday() == 5: # Saturday
                exp_date = current_time + timedelta(days=2)
            else:
                exp_date = current_time
        else:
            # Swing target: 7 days out
            exp_date = current_time + timedelta(days=7)

        # Standardize expiration string formatting (YYYY-MM-DD)
        expiration_str = exp_date.strftime("%Y-%m-%d")

    # Select Strike Price: At-The-Money (ATM) rounding
    strike_price = int(round(current_price))

    # Map directional parameters
    option_type = "call" if signal == "BUY_CALL" else "put"

    # LIMIT ONLY — limit price = mid, rounded to a penny. NEVER market on 0DTE.
    mid = round((option_bid + option_ask) / 2, 2)
    spread_pct = (option_ask - option_bid) / mid if mid > 0 else 1.0
    if spread_pct > 0.10:
        print(f"[MONITOR] Spread too wide ({spread_pct:.1%}) — illiquid, skip.")
        return None

    # Structured schema for your connected Robinhood options execution tool
    order_ticket = {
        "account_suffix": TARGET_ACCOUNT,
        "underlying": TARGET_INDEX,
        "option_type": option_type,
        "strike": strike_price,
        "expiration": expiration_str,
        "quantity": 2,          # Sized safely for your sandbox risk profile
        "side": "buy_to_open",
        "type": "limit",        # Limit at mid — market orders get slipped on 0DTE
        "limit_price": mid,
        "time_in_force": "day"
    }
    return order_ticket

# ==========================================
# LIVE MCP RELAY — how this gets real data
# ==========================================
# A standalone script cannot call the Robinhood MCP directly (OAuth lives in
# Claude Code). The relay is:
#   1. Claude session pulls live data:
#        get_option_chains  -> real 0DTE/nearest expiration
#        get_option_quotes  -> ATM bid/ask (+ delta, volume)
#        TradingView/UW     -> vwap, emas, net_gex, vold, add
#   2. Claude writes payload.json and runs:  python3 robinhood_bot.py --data payload.json
#   3. Script prints the ticket -> Claude runs review_option_order ->
#      MANUAL APPROVAL -> place_option_order (••••3232). Never auto-fire.
#
# payload.json fields:
#   spot, vwap, ema_5, ema_13, ema_21, net_gex, vold, add,
#   option_bid, option_ask, expiration (from get_option_chains)

MOCK_DATA = {
    "spot": 744.07, "vwap": 743.20,
    "ema_5": 744.50, "ema_13": 744.10, "ema_21": 743.80,
    "net_gex": 890000, "vold": 1, "add": 850,
    "option_bid": 2.10, "option_ask": 2.20,
    "expiration": None  # None -> calendar fallback (mock mode only)
}

if __name__ == "__main__":
    preflight_check()

    if len(sys.argv) == 3 and sys.argv[1] == "--data":
        with open(sys.argv[2]) as f:
            d = json.load(f)
        print(f"[SYSTEM] LIVE payload loaded from {sys.argv[2]}")
    else:
        d = MOCK_DATA
        print("[SYSTEM] MOCK mode (no --data payload given) — ticket is a dry run.")

    # Run the selector loop
    action_signal = evaluate_options_strategy(
        d["spot"], d["vwap"], d["ema_5"], d["ema_13"], d["ema_21"],
        d["net_gex"], d["vold"], d["add"]
    )

    # Generate a 0DTE contract ticket
    options_ticket = generate_options_ticket(
        action_signal, d["spot"], d["option_bid"], d["option_ask"],
        trade_style="0DTE", chain_expiration=d.get("expiration")
    )

    if options_ticket:
        print(f"\n[🔥 CRITERIA MET] Generating Options Execution Payload:")
        print(json.dumps(options_ticket, indent=2))
    else:
        print("\n[💤 SAFE REGIME] Flow parameters neutral. No options orders drafted.")
