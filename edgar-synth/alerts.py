"""Alert delivery: macOS notification (osascript) + optional ntfy.sh phone push.

ntfy topic resolves in this order:
  1. alerts.ntfy_topic in config.yaml
  2. $NTFY_TOPIC env var  (fallback — same topic the UW dashboard uses)
Keeping the topic in the env means a repo->Mac config sync can't silently
blank it (the 2026-07-24 failure: config shipped ntfy_topic:"" and a week of
alerts fired to nowhere). Set NTFY_TOPIC in ~/.zshrc, subscribe in the ntfy
app. If NEITHER is set we log a warning so the silence can't hide again.
"""
import os
import logging
import subprocess

import requests

log = logging.getLogger("alerts")


def send(cfg, ticker, entry, verdict, score, price):
    """cfg = config['alerts']."""
    title = f"EDGAR {verdict['direction'].upper()} {ticker} [{score:.0f}]"
    body = (f"{entry['form']} conv={verdict['conviction']}/10 px={price or '?'}\n"
            f"{verdict['reason'][:180]}")

    if cfg.get("macos_notification"):
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{_esc(body)}" with title "{_esc(title)}" sound name "Glass"'],
                timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            log.warning("osascript failed: %s", e)

    topic = cfg.get("ntfy_topic", "") or os.environ.get("NTFY_TOPIC", "")
    if topic:
        try:
            requests.post(f"https://ntfy.sh/{topic}",
                          data=body.encode(),
                          headers={"Title": title,
                                   "Priority": "high",
                                   "Tags": "chart_with_upwards_trend"
                                   if verdict["direction"] == "bull" else "chart_with_downwards_trend"},
                          timeout=10)
        except requests.RequestException as e:
            log.warning("ntfy push failed: %s", e)
    else:
        log.warning("ALERT fired but NO ntfy topic (config ntfy_topic and "
                    "$NTFY_TOPIC both empty) — phone push skipped: %s", title)

    log.info("ALERT %s", title)


def _esc(s):
    return s.replace('"', "'").replace("\\", "")
