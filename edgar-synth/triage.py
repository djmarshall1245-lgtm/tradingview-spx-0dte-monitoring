"""Phase 2: two-stage triage.

Stage 1 (rules, <1ms): form-type priority + universe membership (done in run.py).
Stage 2 (LLM, 1-5s): materiality classifier on the primary document text.
Returns strict-JSON verdict: direction / conviction / reason / items.
"""
import os
import re
import json
import logging

import requests

log = logging.getLogger("triage")

SYSTEM = (
    "You are a buy-side analyst triaging SEC filings on under-covered US small/mid caps. "
    "Judge ONLY what is material enough to move the stock within hours. "
    "Dilution (S-3, 424B5, ATMs), covenant waivers, going-concern language, customer "
    "concentration loss, delistings = bearish. Activist 13Ds, tender offers, unsolicited "
    "bids, major contract wins, debt retirement = bullish. Routine housekeeping "
    "(director elections, annual meeting results, boilerplate amendments) = neutral, "
    "conviction 1-2. Respond with ONLY a JSON object, no markdown fences, no prose: "
    '{"direction": "bull"|"bear"|"neutral", "conviction": 1-10, '
    '"reason": "<one line, cite the specific detail>", "items": ["<8-K item codes or key facts>"]}'
)


def classify(cfg, entry, ticker, doc_text):
    """cfg = config['llm']. Returns verdict dict; conviction 0 on failure."""
    fallback = {"direction": "neutral", "conviction": 0, "reason": "llm_error", "items": []}
    if not doc_text:
        return {"direction": "neutral", "conviction": 0, "reason": "no_document_text", "items": []}

    user_msg = (
        f"Form: {entry['form']}\nCompany: {entry['title']}\nTicker: {ticker}\n"
        f"Filed: {entry['filed_at']}\n\nFiling text (truncated):\n{doc_text}"
    )
    try:
        raw = _call(cfg, user_msg)
        verdict = json.loads(_strip_fences(raw))
        verdict["conviction"] = max(0, min(10, int(verdict.get("conviction", 0))))
        if verdict.get("direction") not in ("bull", "bear", "neutral"):
            verdict["direction"] = "neutral"
        verdict.setdefault("reason", "")
        verdict.setdefault("items", [])
        return verdict
    except Exception as e:  # noqa: BLE001 - any triage failure -> neutral, keep loop alive
        log.warning("classify failed %s: %s", entry["accession"], e)
        return fallback


def _call(cfg, user_msg):
    key = os.environ.get(cfg.get("api_key_env", "LLM_API_KEY"), "")
    timeout = cfg.get("timeout_sec", 45)

    if cfg["provider"] == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": cfg["model"], "max_tokens": 400, "system": SYSTEM,
                  "messages": [{"role": "user", "content": user_msg}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]

    # openai-compatible (MiniMax M3 local server, etc.)
    r = requests.post(
        f"{cfg['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={"model": cfg["model"], "max_tokens": 1000, "temperature": 0,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user_msg}]},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _strip_fences(text):
    # MiniMax M3 prefixes a <think>...</think> reasoning block — drop it.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
