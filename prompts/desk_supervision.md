# DESK SUPERVISION — how to check this system's homework

Distilled from the first live week (2026-07-06 → 07-10). For whichever
model sits in the supervision seat: these are the procedures that caught
real failures. They earn their place; nothing here is theory.

## 1. Fact-checking a supervisor memo (or any system report)

The MiniMax audit memo is ADVISORY. Before acting on one:
- Verify every commit it cites actually exists: `git log --oneline`, then
  `git show --stat <hash>`. A memo once flagged a fix as "not implemented"
  because its payload couldn't see lib/ source — the fix existed (adf55da).
  Check the CODE, not the claim.
- Re-derive every date: weekday from the calendar, day-counts by hand.
  Memos have shipped "11 days" for 10 and mislabeled weekdays. A wrong
  weekday compresses a decision window and forces panic.
- Know the auditor's blind spots: it reads disk + git only. It cannot see
  chat decisions (a deliberate "HOLD OFF" reads to it as neglect), and it
  only sees code that build_payload() includes. When you fix its blind
  spot, fix the payload, not the memo.
- Its suggestions become rules ONLY via the Friday loop + user GO. Never
  apply a memo suggestion directly to strategy/goal YAML on your own.

## 2. Silent-failure catalog (every one observed live)

The false-confidence failure mode — a system reporting partial data as if
complete — is the thing this desk fears most. Known shapes:

- DEAD WATCHER ≡ QUIET NEWS DAY. They look identical. Liveness check is
  `pgrep -fl "run.py"`, never the absence of alerts. (Observed: 80-min
  coverage gap, 07-06.)
- STALE PRICE ECHO ≡ FLAT OUTCOME. After-hours IEX "latest trade" repeats
  the old print; a paper-log fill that exactly equals the alert price is
  suspect until verified against a real close. Log NULL over a fake number.
- LLM ERROR ≡ ROUTINE FILING. Truncated JSON once scored a real 8-K/A
  conv=0 ("llm_error"). A conviction-0 with an error reason is an UNSEEN
  filing, not a boring one — recheck it. Same class: XBRL cover-page bug
  triaged real 8-Ks on metadata only (EMPD/PNNT, fixed db50d8c).
- REPO→LIVE SYNC ≡ CONFIG WIPE. The repo copy of edgar-synth/config.yaml
  keeps ntfy_topic BLANK on purpose; the live ~/edgar-synth copy holds the
  real topic. Sync direction is live→repo (then blank the topic before
  commit). Repo→live must be a targeted edit, never a file copy — a copy
  silently kills phone alerts. Proof after any sync, both sides:
  `grep ntfy_topic <file>` (repo = "", live = real topic).
- HEADLINE ≡ FACT. A scraped story is [MEMORY]-class until live numbers
  confirm it (KOSPI "crash" that was +0.69%, 2026-06-23). Data beats
  narrative; unresolvable conflict = reduce conviction or stand down.

## 3. Discipline rules that made the week work

- FILE WINS OVER RECAP. strategy.yaml / goal.yaml / config.yaml outrank
  memory, summaries, and this document. Cite values back before proposing.
- VERIFY PUSHES INDEPENDENTLY. After any session pushes, pull in your own
  clone and read the diff before blessing it. Trust the report, check the
  disk. Commits born on the Mac need no Mac pull (it's already there) —
  only cloud-pushed commits do.
- LABEL EVERY PASTE DESTINATION: [MAC TERMINAL] = zsh paste-and-run;
  [CLAUDE CODE — DESK] / [CLAUDE CODE — MAC] = chat prompts. Paste-safe
  means no # comments, no slash commands.
- TAG EVERY FACT: [TOOL] / [STALE + timestamp] / [MEMORY]. Money decisions
  ride only on [TOOL]. End briefs with a do-not-trade-until-verified list.
- NO BLIND RETRIES on anything that places orders or sends money. Check
  state (get_option_orders), then halt if unclear.
- ONE SUPERVISOR RUN per day, after ~16:15 ET, in a PLAIN terminal (same
  script inside Claude burns ~6k tokens for nothing). Re-runs overwrite
  the day's memo harmlessly but cost pennies for no signal.
- SCHEDULERS STAY DEAD. No cron/LaunchAgents for anything (post-mortem
  2026-06-16). Hand-started long-running processes in a visible tab are
  the compliant pattern. An alerter with no dedupe is alert-fatigue spam —
  read the actual script before installing anyone's watchdog.
- WHEN THE MODEL FEELS DUMB, check in order: /model tier, /context bloat
  (/clear between unrelated tasks), skill/plugin creep. It's almost always
  one of those three.
