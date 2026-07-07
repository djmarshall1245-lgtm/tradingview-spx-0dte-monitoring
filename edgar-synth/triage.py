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


def _repair_json(raw):
    """Attempt to parse truncated JSON from LLM output. Returns dict or None."""
    text = _strip_fences(raw)
    # Strategy 1: find the last complete {...} substring
    # Walk backward to find a closing brace and try parsing from the first {
    start = text.find("{")
    if start == -1:
        return None
    # Try the full text first (maybe just needs fence stripping)
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        pass
    # Strategy 2: truncate at the last '}' and try
    last_brace = text.rfind("}")
    if last_brace > start:
        try:
            return json.loads(text[start:last_brace + 1])
        except json.JSONDecodeError:
            pass
    # Strategy 3: close unterminated strings/objects
    fragment = text[start:]
    for suffix in ['"}', '"}]', '"]}', '", "items": []}', '"]}']:
        try:
            return json.loads(fragment + suffix)
        except json.JSONDecodeError:
            pass
    return None


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
    except json.JSONDecodeError as e:
        log.warning("JSON decode failed %s: %s — attempting repair", entry["accession"], e)
        # Layer 1: try to repair the truncated JSON
        repaired = _repair_json(raw)
        if repaired is not None:
            log.warning("JSON repair succeeded for %s", entry["accession"])
            repaired["conviction"] = max(0, min(10, int(repaired.get("conviction", 0))))
            if repaired.get("direction") not in ("bull", "bear", "neutral"):
                repaired["direction"] = "neutral"
            repaired.setdefault("reason", "")
            repaired.setdefault("items", [])
            return repaired
        # Layer 2: one LLM retry with nudge
        log.warning("JSON repair failed for %s, retrying LLM", entry["accession"])
        try:
            retry_msg = user_msg + "\n\nIMPORTANT: Return ONLY valid JSON. No truncation."
            raw2 = _call(cfg, retry_msg)
            verdict2 = json.loads(_strip_fences(raw2))
            verdict2["conviction"] = max(0, min(10, int(verdict2.get("conviction", 0))))
            if verdict2.get("direction") not in ("bull", "bear", "neutral"):
                verdict2["direction"] = "neutral"
            verdict2.setdefault("reason", "")
            verdict2.setdefault("items", [])
            return verdict2
        except Exception as e2:  # noqa: BLE001
            log.warning("LLM retry also failed for %s: %s", entry["accession"], e2)
            return fallback
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
