# Fireline / Treeline — definition & sourcing

**Fireline and Treeline are the /ES futures session HIGH and LOW.**
They are NOT pivots and are NOT plotted by the AR Squeeze script.
Never compute them from pivot math. Pull the real futures extremes.

## Definitions
- 🔥 **Fireline = ES High** → overhead **resistance** (above price)
- 🌲 **Treeline = ES Low**  → **support** (below price)

## How to pull (the ONLY correct method)
1. `data_get_ohlcv` on **ES1!** with `summary: true`.
2. Take the session **High** → Fireline, session **Low** → Treeline.
3. Convert /ES → SPX: ES trades ~5–10 pts above SPX and the offset
   **fluctuates** intraday — compute the live offset from current
   ES1! vs SPX quotes, don't assume a fixed number.
4. Tag everything `[TOOL]` and name the tool used.

## Session window
- **Default = today's regular session** (covers RTH 9:30–4:00 ET) — use this
  for 0DTE intraday.
- For the **full overnight Globex** range, pull more bars / anchor to the
  Globex open and say so explicitly.

## How they drive bias
- SPX **above Fireline (ES high)** reclaimed → bullish, favor **calls**,
  target the next Voodoo level up.
- SPX **below Treeline (ES low)** lost → bearish, favor **puts**,
  target the next Voodoo level down.
- SPX **inside** the Fireline–Treeline range → chop, stay flat until a break.

## Do NOT
- ❌ Do not compute Fireline/Treeline from floor pivots (R1/PP/PDH/etc.).
- ❌ Do not read them from `data_get_pine_labels` — the script doesn't plot them.
- ❌ Do not flip the roles. Fireline is the HIGH (resistance); Treeline is the
  LOW (support).
