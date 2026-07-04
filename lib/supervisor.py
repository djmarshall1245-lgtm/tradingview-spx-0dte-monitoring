"""Supervisor — independent end-of-day contradiction audit via MiniMax M3.

Packages the day's on-disk state (strategy, goal, positions, journal, commit
log, freshness) and sends it to a SECOND model (minimax/minimax-m3 on
OpenRouter) whose only job is to flag contradictions and routine gaps.
Advisory only: prints a report, writes nothing, trades nothing.

  python run.py --supervise            # audit as of today
  python run.py --supervise --asof 2026-07-02

Needs MINIMAX_API_KEY (MiniMax platform, pay-as-you-go) exported in the
shell (~/.zshrc, same pattern as the Alpaca keys — never in this repo).
Falls back to OPENROUTER_API_KEY if MiniMax's key is absent. Cost: 1-2
cents/run (~8k tokens in, up to ~12k out — M3 is a reasoning model and
spends most of its output budget thinking before the report).

MANUAL TRIGGER ONLY. Never wire this into a LaunchAgent/cron — the
scheduled-job token burn of 2026-06-16 applies (scratch/post_mortem_launchagents.md).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "journal" / "audits"     # the supervisor's own memory
PRIOR_AUDITS_FED_BACK = 3                    # how many past memos it re-reads

# Provider picked by which key is exported: MiniMax native first, then OpenRouter.
PROVIDERS = [
    ("MINIMAX_API_KEY", "https://api.minimax.io/v1/chat/completions", "MiniMax-M3"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions", "minimax/minimax-m3"),
]
PER_FILE_CHAR_CAP = 15_000          # keeps the payload (and cost) bounded

PAYLOAD_FILES = [
    "strategy/strategy.yaml",
    "strategy/goal.yaml",
    "config.yaml",
    "positions.yaml",
    "journal/trades.jsonl",
    "journal/hypotheses.jsonl",
]


def _read_capped(rel):
    p = ROOT / rel
    if not p.exists():
        return f"<< {rel}: MISSING >>"
    text = p.read_text(errors="replace")
    if not text.strip():
        return f"<< {rel}: EXISTS BUT EMPTY >>"
    if len(text) > PER_FILE_CHAR_CAP:
        return text[:PER_FILE_CHAR_CAP] + f"\n<< TRUNCATED at {PER_FILE_CHAR_CAP} chars >>"
    return text


def _git_log():
    try:
        out = subprocess.run(
            ["git", "log", "--since=7 days ago",
             "--format=%h %ad %s", "--date=format:%a %Y-%m-%d"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "<< no commits in the last 7 days >>"
    except Exception as e:
        return f"<< git log unavailable: {e} >>"


def _freshness():
    """Last-touched dates for the artifacts the routine is supposed to feed."""
    lines = []
    for label, pattern in [
        ("chain snapshots (data/snapshots)", "data/snapshots/*.json"),
        ("screenshots (data/shots)", "data/shots/*.png"),
        ("trade journal", "journal/trades.jsonl"),
        ("hypotheses log", "journal/hypotheses.jsonl"),
    ]:
        paths = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not paths:
            lines.append(f"- {label}: NO FILES")
            continue
        newest = paths[-1]
        stamp = datetime.fromtimestamp(newest.stat().st_mtime).strftime("%a %Y-%m-%d %H:%M")
        lines.append(f"- {label}: newest = {newest.name}, modified {stamp} "
                     f"({len(paths)} file(s))")
    return "\n".join(lines)


def _system_prompt():
    raw = (ROOT / "prompts" / "supervisor.md").read_text()
    # strip the yaml frontmatter block; the charter below it is the prompt
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            raw = raw[end + 3:]
    return raw.strip()


def _prior_audits():
    """Last few memos, oldest first — the supervisor's memory across days."""
    if not AUDIT_DIR.exists():
        return "<< no prior audits — this is the first run >>"
    memos = sorted(AUDIT_DIR.glob("*.md"))[-PRIOR_AUDITS_FED_BACK:]
    if not memos:
        return "<< no prior audits — this is the first run >>"
    chunks = []
    for m in memos:
        text = m.read_text(errors="replace")
        if len(text) > 4000:
            text = text[:4000] + "\n<< TRUNCATED >>"
        chunks.append(f"--- {m.name} ---\n{text}")
    return "\n\n".join(chunks)


def build_payload(asof=None):
    now = datetime.now(ZoneInfo("America/New_York"))
    asof = asof or now.date().isoformat()
    parts = [
        f"TODAY (verified by system clock): {now:%A %Y-%m-%d %H:%M %Z}",
        f"AUDIT AS-OF DATE: {asof}",
        "",
        "=== FRESHNESS ===",
        _freshness(),
        "",
        "=== GIT LOG (last 7 days) ===",
        _git_log(),
        "",
        "=== PRIOR AUDITS (your own memory — compare today against these) ===",
        _prior_audits(),
    ]
    for rel in PAYLOAD_FILES:
        parts += ["", f"=== {rel} ===", _read_capped(rel)]
    return "\n".join(parts)


def run(asof=None):
    key = url = model = None
    for env_name, provider_url, provider_model in PROVIDERS:
        if os.environ.get(env_name):
            key, url, model = os.environ[env_name], provider_url, provider_model
            break
    if not key:
        sys.exit(
            "MINIMAX_API_KEY is not set. Add it to ~/.zshrc (same pattern "
            "as the Alpaca keys):\n"
            '  read -s "k?MiniMax key: " && echo && '
            "printf '\\nexport MINIMAX_API_KEY=%s\\n' \"$k\" >> ~/.zshrc "
            "&& unset k && source ~/.zshrc"
        )

    payload = build_payload(asof)
    import requests
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0.2,
            # M3 is a REASONING model: it thinks in a visible <think> block
            # before writing. 3000 hit the cap mid-thought and produced no
            # report (observed first live run, Sat 2026-07-04) — leave room.
            "max_tokens": 12000,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": payload},
            ],
        },
        timeout=180,
    )
    if resp.status_code != 200:
        sys.exit(f"API error {resp.status_code} from {url}: {resp.text[:500]}")
    body = resp.json()
    if not body.get("choices"):
        # MiniMax can 200 with an error object (base_resp) instead of choices
        sys.exit(f"API returned no choices: {json.dumps(body)[:500]}")
    raw = body["choices"][0]["message"]["content"].strip()
    # Strip the reasoning scratchwork — the memo keeps only the report.
    # An UNCLOSED <think> means output was truncated mid-thought: no report.
    if raw.startswith("<think>") and "</think>" not in raw:
        report = ""
    else:
        report = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if not report:
        finish = body["choices"][0].get("finish_reason", "?")
        sys.exit(
            f"Model produced only <think> scratchwork and no report "
            f"(finish_reason={finish}) — likely hit max_tokens mid-thought. "
            "Re-run; if it repeats, raise max_tokens in lib/supervisor.py. "
            "No memo saved."
        )
    usage = body.get("usage", {})
    print(report)
    print(f"\n[supervisor: {model} · {usage.get('prompt_tokens', '?')} in / "
          f"{usage.get('completion_tokens', '?')} out]")

    # persist the memo — this IS the second brain. Next run reads it back.
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    asof_stamp = asof or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    memo = AUDIT_DIR / f"{asof_stamp}.md"     # re-run same day = overwrite, latest wins
    memo.write_text(report + "\n")
    print(f"[memo saved: {memo.relative_to(ROOT)}]")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
