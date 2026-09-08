# G13 Control

**1.1.0 known issue:** M1 has been confirmed readable; the user reports scrambled
characters on M2–M4. See [the proposed follow-up](../TODO.md).

A native GTK 3 / Ayatana tray app for the Linux G13 driver. Open **G13 settings**
from the panel's G13 indicator. Closing the window leaves the app running.
The application menu also contains **G13 Control**.

## Install and run

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
./build_driver.sh --force
./scripts/install-g13-tray
/usr/bin/python3 ~/.local/share/g13-tray/g13_tray.py
```

Install the driver service using `scripts/g13ctl install` if it is not already
installed. The tray installer enables desktop login autostart. GNOME requires
AppIndicator support (Ubuntu normally includes it). Other panels must support
StatusNotifierItem indicators. A single-instance lock prevents duplicate trays.

## Profiles and keys

Each tab controls one profile, its backlight colour, screen source, and G1–G22
bindings. Choose a Linux key or an existing macro from the dropdown. The macro
list reads `~/.g13/macro-*.properties`; create new macros in the repository's Java
macro editor. Disabled entries produce no input.

**Save & apply** backs up the four bindings files and restarts the driver service.
It preserves other properties and joystick mappings. Changes made by an external
editor after the window opened cause a save conflict; reopen the app to reload.
Secrets are stored in `~/.config/g13/tray.json` with permissions `0600`.
Backups are in `~/.g13/backups/<timestamp>/`.

Saving enables `mode_profiles=1` in all four binding files:

- Physical M1/M2/M3/MR select profiles 0–3; MR is M4 in the app.
- LCD buttons L1–L4 select the same profiles.
- M1 always renders the existing built-in system stats.
- The mode LED and LCD backlight follow the selected profile.
- G1 on the physical keypad is `G0` in the legacy properties format. The app
  performs this conversion; do not rename property keys to match printed labels.

The driver remains compatible with its legacy page-only selection when
`mode_profiles` is absent. Unlike the legacy mode, the new mode reserves physical
M1/M2/M3/MR for profile switching.

## Screen connections

New providers run in a background thread every 60 seconds. The driver reads their
five-line, 26-character cache files instead of making network requests. Errors
replace the screen with a status message; no credentials are printed. **Refresh
stats** uses saved settings. Saving a connection activates it. Quit stops polling;
currently the last cache remains on the display until the tray starts again.

| Screen | Data | Setup / limitation |
| --- | --- | --- |
| System stats | Existing CPU, memory, GPU, network, disk and sensor display | Fixed on M1 |
| Steam | Online friend count and up to three names | Steam Web API key and SteamID64; private friend lists may deny access |
| Discord | Server name, approximate members and online count | Bot token and server ID; bot must belong to the server. Does not read personal DMs or automate a user account |
| Codex local | Input/output counters from the most recently modified local session | No key. Reads token events in the last 2 MB of session JSONL; local schema is best effort. Not account-wide quota or billing |
| OpenAI API | Today's UTC organisation input/output token totals | `OPENAI_ADMIN_KEY`; API Platform usage, not a personal Codex/ChatGPT allowance |
| Claude API | Today's UTC organisation input/output totals including input cache tokens | `ANTHROPIC_ADMIN_KEY`; API usage, not Claude Pro/Max remaining quota |
| Antigravity / text file | Up to four exported lines plus file age | No verified public quota API. Select a regular local text file you maintain/export; this app does not create an Antigravity export automatically |
| Custom text | Up to five lines | Separate lines with `|` |
| Keep existing command | Existing profile-zero page command | Compatibility option; legacy shell commands still run inside the driver and may block it |

No API credentials were available in the driver environment during installation.
Steam, Discord and organisation API responses were tested with fixtures, not live
account authentication. Codex local counters were verified against an available
session. Physical button presses and backlight appearance still need a user check.

### Verified API references

- [Steam ISteamUser](https://partner.steamgames.com/doc/webapi/ISteamUser)
- [Discord guild resource](https://docs.discord.com/developers/resources/guild)
- [OpenAI organisation usage](https://platform.openai.com/docs/api-reference/usage)
- [Claude Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)
- [Antigravity interactive quota panel](https://antigravity.google/docs/cli/commands/usage)

## Verification and development

```bash
/usr/bin/python3 -m unittest discover -s tests -v
./tests/run-driver-tests.sh
```

The C++ test replaces USB transfers and verifies loading multiple properties,
long lines, mode selection, held-selector debouncing, and release of old input
bindings. Python tests cover backup/preservation, conflict detection, validation,
provider pagination, error redaction, LCD bounds, and local token counters.
For a desktop smoke test use a temporary `HOME` and run `app/g13_tray.py
--smoke-test`; it exits automatically and saves `/tmp/g13-tray-preview.png`.

Re-run the installer after app changes. Restart the tray to load the new Python
files. The driver build must be forced after header edits because the existing
Makefile does not track header dependencies.

To remove autostart, delete `~/.config/autostart/g13-control.desktop`. Quit from
the tray menu. To restore previous bindings, copy the four files from a backup
folder into `~/.g13/`, then run `systemctl --user restart g13-driver.service`.
