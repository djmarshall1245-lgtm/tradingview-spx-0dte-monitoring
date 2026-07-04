"""Supervisor — independent end-of-day contradiction audit via MiniMax M3.

Packages the day's on-disk state (strategy, goal, positions, journal, commit
log, freshness) and sends it to a SECOND model (minimax/minimax-m3 on
OpenRouter) whose only job is to flag contradictions and routine gaps.
Advisory only: prints a report, writes nothing, trades nothing.

  python run.py --supervise            # audit as of today
  python run.py --supervise --asof 2026-07-02

Needs OPENROUTER_API_KEY exported in the shell (~/.zshrc, same pattern as
the Alpaca keys — never in this repo). Cost: ~1 cent/run at M3 pricing
($0.30/M in, $1.20/M out; ~20-30k tokens in, ~1k out).

MANUAL TRIGGER ONLY. Never wire this into a LaunchAgent/cron — the
scheduled-job token burn of 2026-06-16 applies (scratch/post_mortem_launchagents.md).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

MODEL = "minimax/minimax-m3"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
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
    ]
    for rel in PAYLOAD_FILES:
        parts += ["", f"=== {rel} ===", _read_capped(rel)]
    return "\n".join(parts)


def run(asof=None):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit(
            "OPENROUTER_API_KEY is not set. Add it to ~/.zshrc (same pattern "
            "as the Alpaca keys):\n"
            '  read -s "k?OpenRouter key: " && echo && '
            "printf '\\nexport OPENROUTER_API_KEY=%s\\n' \"$k\" >> ~/.zshrc "
            "&& unset k && source ~/.zshrc"
        )

    payload = build_payload(asof)
    import requests
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "temperature": 0.2,
            "max_tokens": 3000,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": payload},
            ],
        },
        timeout=180,
    )
    if resp.status_code != 200:
        sys.exit(f"OpenRouter error {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    report = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    print(report.strip())
    print(f"\n[supervisor: {MODEL} · {usage.get('prompt_tokens', '?')} in / "
          f"{usage.get('completion_tokens', '?')} out]")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
