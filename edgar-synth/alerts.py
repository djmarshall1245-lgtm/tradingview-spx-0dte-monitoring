"""Alert delivery: macOS notification (osascript) + optional ntfy.sh phone push.

ntfy: set alerts.ntfy_topic in config to a hard-to-guess string, install the
ntfy app on your phone, subscribe to that topic. Free, no signup.
"""
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

    topic = cfg.get("ntfy_topic", "")
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

    log.info("ALERT %s", title)


def _esc(s):
    return s.replace('"', "'").replace("\\", "")
