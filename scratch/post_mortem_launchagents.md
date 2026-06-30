# Post-mortem: LaunchAgent overnight token burn (FIXED 2026-06-16)

Root cause of "something ran overnight and used all my tokens": two macOS
LaunchAgents on the trading Mac auto-firing Claude Code CLI **unattended**.
They live in `~/Library/LaunchAgents/` on the Mac — NOT in this repo/container,
which is why an in-session scan looks clean.

- `com.andrereynolds.spx.briefing.plist` → `premarket_briefing.sh`. Fired
  ~8:53 AM ET every weekday: a ~3,000-word prompt → 10+ MCP tool calls → a full
  Opus conversation, all before you opened the laptop. **Main culprit.**
- `com.andrereynolds.lotteryscanner.plist` → lottery scanner. Same pattern.

**Lesson learned:** first disabled 2026-06-15 with a plain `launchctl unload` —
that did NOT stick. `unload` is session-only; macOS reloaded the still-present,
still-enabled `.plist` files at the next login and the briefing **re-fired at
8:53 the next morning**. Killed for good 2026-06-16 with the method below.

## Kill for good (Mac terminal, NOT the web session)

You must `bootout` + `disable` (writes launchd's persistent override DB,
survives reboot/login) AND move the `.plist` out so login has nothing to reload:

```bash
for label in com.andrereynolds.spx.briefing com.andrereynolds.lotteryscanner; do
  launchctl bootout gui/$(id -u)/$label 2>/dev/null
  launchctl disable gui/$(id -u)/$label
done
mv ~/Library/LaunchAgents/com.andrereynolds.spx.briefing.plist{,.disabled}
mv ~/Library/LaunchAgents/com.andrereynolds.lotteryscanner.plist{,.disabled}
```

## Verify (all must be clean)

- `launchctl list | grep -Ei 'briefing|lottery'` → no output
- `ls ~/Library/LaunchAgents/ | grep -Ei 'briefing|lottery'` → only `*.disabled`
- `launchctl print gui/$(id -u)/com.andrereynolds.spx.briefing` → "Could not find"

To re-enable intentionally: rename back + `launchctl bootstrap gui/$(id -u) <plist>`.
