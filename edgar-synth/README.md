# edgar-synth

EDGAR watcher → LLM triage → synthesis score (filing × short structure × options flow) → alert + paper log.
**No execution anywhere. Alerts and a paper log only.** The log decides if the edge is real.

## Phase map
| Phase | Module | What it does |
|---|---|---|
| 1 Watcher | `edgar.py` | Polls SEC `getcurrent` Atom feed every 2s, dedupes by accession, filters to target forms + your universe |
| 2 Triage | `triage.py` | Rules pass (form/universe) → LLM materiality verdict: direction, conviction 1-10, reason |
| 3 Synthesis | `enrich.py` + `synthesis.py` | UW short data + flow-alert skew joined with the verdict → compound score 0-100 |
| 4 Alert+Log | `alerts.py` + `paperlog.py` | macOS notification + optional ntfy phone push; every signal logged to SQLite with +5m/+30m/+1d price fills |

## Setup (on the 2012 Mac)
```bash
cd edgar-synth
pip3 install -r requirements.txt

# 1. REQUIRED: edit config.yaml -> sec_user_agent with your name + email.
#    SEC blocks undeclared bots. This is non-negotiable.
# 2. Secrets:
export FMP_API_KEY="..."           # add to ~/.zshrc
export LLM_API_KEY="..."           # MiniMax key, or ANTHROPIC_API_KEY if provider=anthropic
#    UW token: already at ~/.uw_credentials (UW_TOKEN=... or raw token line)
# 3. Point config.yaml llm.base_url/model at your MiniMax M3 endpoint,
#    or set provider: anthropic + model: claude-haiku-4-5.
```

## Run
```bash
python3 run.py            # main loop, 6am-10pm ET weekdays
python3 run.py --once     # single cycle, debug
python3 run.py --stats    # paper-log hit rate at +30m

python3 tests/test_offline.py   # parser/scoring tests, no network
```

Watchdog (cron, absolute path — cron PATH is minimal):
```
*/5 6-22 * * 1-5 /FULL/PATH/edgar-synth/watchdog.sh
```

## Success criteria (verify before any capital)
1. **Latency**: `ts_detected − ts_filed` < 5 min consistently (EDGAR publishes 1–3 min after acceptance; our poll adds ≤ ~10s on top of that).
2. **Hit rate**: ≥ 60% of alerted signals move in the verdict direction at +30m (`python3 run.py --stats`).
3. **Frequency**: enough alerts to matter. If < ~2/week after 2 weeks, widen `target_forms` or the universe band before concluding anything.

Run 2–4 weeks paper. Only then talk about execution.

## Known limits (v1, deliberate)
- **After-hours fills**: most 8-Ks drop post-close; `p5m`/`p30m` use FMP's last/extended price. Treat `p1d` (next session) as the honest fill for post-close filings.
- **Primary-doc heuristic**: largest .htm in the filing index. Catches the main document; exhibits (where covenant waivers hide) are v2 — add exhibit fetch once base hit rate justifies more SEC requests per filing.
- **13D vs 13G**: 13G (passive) intentionally excluded — activist intent is the signal.
- **Form 4 insider buys**: excluded from v1 to keep noise down; strong candidate for v2 (cluster-buy detection).
- **UW field types**: `fee_rate` and `total_premium` arrive as strings — `_to_float()` handles it (same pattern as your squeeze scanner).

## Tuning knobs
- `alert_score_min` / `alert_conviction_min`: start strict (60/7), loosen if too quiet.
- `synthesis` weights: conviction 0.5 / short 0.3 / flow 0.2. Revisit after 50+ logged signals — the paper log tells you which factor actually predicts.
- `universe`: $100M–$2B, vol > 200k. The smaller the cap band, the less HFT competition and the worse the fills — the log will show you where the tradeoff lives.
