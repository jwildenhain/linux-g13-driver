# G13 Control

**Display fix:** the lowercase font-table shift reported in 1.1.0 is fixed in
the current source and tested at pixel level. Physical confirmation is pending.
See [the implementation checklist](../TODO.md).

A native GTK 3 / Ayatana tray app for the Linux G13 driver. Open **G13 settings**
from the panel's G13 indicator. Closing the window leaves the app running.
The application menu also contains **G13 Control**.

## Install and run

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
./build_driver.sh --force
# Optional: fetch the complete game-profile collection before installing.
/usr/bin/python3 tools/import_game_profiles.py
./scripts/install-g13-tray
/usr/bin/python3 ~/.local/share/g13-tray/g13_tray.py
```

Install the driver service using `scripts/g13ctl install` if it is not already
installed. The tray installer enables desktop login autostart. GNOME requires
AppIndicator support (Ubuntu normally includes it). Other panels must support
StatusNotifierItem indicators. A single-instance lock prevents duplicate trays.

## Keypad popup and profile library

Choose **Configure G13 buttons…** from the tray menu or main settings window.
The game list groups related source modes into one entry. Badges identify single
or multiple modes, matching assignments, identical modes and unsupported actions.
Search by game name or repository. **Currently saved on G13** shows the real saved
M1–M4 assignments; **Imported local snapshots** is an older library snapshot.

For each source mode, choose its destination **M1–M4** or **Skip**. Multi-mode
profiles default to their corresponding destinations; single-mode profiles can
be placed on any destination. A destination can only be used once in a batch.
For example, route Overwatch 2's source M1/M2/M3 to M1/M2/M3, or route Skyrim's
single mode to M4. To copy saved M1 to M3, skip the existing source M3 card first.

Click **Edit M1**, **Edit M2**, etc. to choose a source mode, then click a control
on the keypad to edit it. **Show assigned keys** switches the drawing between
physical labels and proposed assignments. Compact labels fit the buttons; hover
for the full current/proposed assignment.

The four arrow controls at the joystick edit up/left/right/down. **T1** is the
thumb button to the joystick's left; **T2** is the button below. All six use the
same key and macro selector and save independently for each destination mode.
Assigning joystick directions enables `stick_mode=keys` for that destination;
the review summary explicitly says that analogue mode will be turned off.
If no joystick directions are included or edited, its mode is preserved. Thumb buttons alone do
not change joystick mode. The driver maps T1/T2 to `G33`/`G34` and joystick
up/left/right/down to `G36`/`G37`/`G38`/`G39`.

 **Current → proposed** shows the destination's saved key
and proposed value. Changed keys are highlighted. Draft edits survive switching
to another game while the popup is open; closing it discards unapplied drafts.
**Duplicates & import notes** separates exact source matches, identical supported
control assignments, partial overlaps, missing assignments and unsupported actions.
Library comparisons describe original sources, not subsequent manual edits.
Actual saved-mode comparisons consider all 28 editable controls.

**Review & apply assignments…** lists the number of changed keys per destination.
Cancel leaves settings untouched. Apply validates every selected destination
before writing, makes one backup folder for all affected modes, and restarts the
driver once. An external-edit conflict prevents the entire batch. A write failure
triggers restoration of already-written modes and removal of newly created
macros; an unsuccessful restoration reports the backup path for manual recovery.
Unchanged modes, screen content, lighting and unselected control assignments are preserved.

See [the full library audit](PROFILE_AUDIT.md) for mode groupings, exact matches,
and closest partial overlaps. No duplicate entries are removed automatically.

The installer copies the local `data/g13-keymaps.json` collection into the app
when available, together with the keypad image. The dataset stays local and is
not bundled in Git. Without it, saved-mode copying and manual editing still work.
Numeric and symbolic Linux keys and key combinations are converted. Canonical
LEFT/DOWN and STICK_* source labels import thumb buttons and directions too. The XML importer translates G23–G29 into canonical controls: all 285 supported thumb/direction assignments now convert. See [the auxiliary audit](AUXILIARY_AUDIT.md). Valid macro
sequences are copied to unused local IDs. Unsupported actions (including TYPE
text scripts), missing macros and reserved buttons are listed in the preview;
the target assignments for those entries are retained. Review these notes before
saving. Unlisted keys also retain their target assignments.

The **Credentials** tray submenu opens individual Steam, Discord, OpenAI API,
Claude API and Antigravity dialogs. Antigravity supports storage only, as explained
below; the other services support connection checks. Secret fields are masked. **Check connection** performs a
read-only check of the entered values without saving them; **Save** stores them
with owner-only permissions and **Remove** clears them. Saving here does not apply
unsaved screen edits. API checks need credentials; no account credentials were
available for live verification during development.

## Profiles and keys

Each M tab controls one key profile and has L1–L4 sub-tabs for four independent screen sources and colours, alongside its G1–G22 bindings. Choose a Linux key or an existing macro from the dropdown. The macro
list reads `~/.g13/macro-*.properties`; create new macros in the repository's Java
macro editor. Disabled entries produce no input.

**Save & apply** backs up the four bindings files and restarts the driver service.
It preserves other properties and joystick mappings. Changes made by an external
editor after the window opened cause a save conflict; reopen the app to reload.
Secrets are stored in `~/.config/g13/tray.json` with permissions `0600`.
Backups are in `~/.g13/backups/<timestamp>/`.

Saving enables `mode_profiles=1` and `mode_screens=1` in all four binding files:

- Physical M1/M2/M3/MR select profiles 0–3; MR is M4 in the app.
- LCD buttons L1–L4 select four screens within the current M profile; assignments and mode LEDs stay unchanged.
- M1/L1 always renders system stats; other screens may also select System stats.
- The mode LED follows the M profile; the backlight colour follows its selected L screen.
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
| System stats | Existing CPU, memory, GPU, network, disk and sensor display | Fixed on M1/L1; optional elsewhere |
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

M1 now shows `CPU <usage>% THR <active> <temperature>C`, then `MEM <usage>% PSU <watts>W`. Active means a logical thread exceeds 5% utilisation over the sampling interval; its first reading is `n/a`. NIC temperature follows speed on the NET row. PSU power uses the Corsair total sensor, with `n/a` when unavailable.

### M1 GPU memory

The GPU row reads `GPU 19% MEM 23% 56C`: GPU utilisation, allocated VRAM as a percentage of total VRAM (rounded to the nearest percent), and GPU temperature in Celsius. It is separate from the system RAM row. NVIDIA uses the first GPU reported by `nvidia-smi`; the DRM fallback uses the first available GPU busy counter and its VRAM/temperature files. Missing measurements show `n/a`.

## Verification and development

```bash
/usr/bin/python3 -m unittest discover -s tests -v
./tests/run-driver-tests.sh
# Optional desktop interaction test, isolated from real settings:
sandbox_home=$(mktemp -d /tmp/g13-ui-check-XXXXXX)
HOME="$sandbox_home" /usr/bin/python3 tests/check_tray_ui.py
```

The C++ test replaces USB transfers and verifies loading multiple properties,
long lines, mode selection, held-selector debouncing, and release of old input
bindings. Python tests cover backup/preservation, conflict detection, validation,
provider pagination, error redaction, LCD bounds, local token counters, XML
conversion, imported macros and target-mode isolation. The GTK check exercises
profile selection, editing, saving, and masked credential save/remove controls.
For a desktop smoke test use a temporary `HOME` and run `app/g13_tray.py
--smoke-test`; it exits automatically and saves `/tmp/g13-tray-preview.png`.

Re-run the installer after app changes. Restart the tray to load the new Python
files. The driver build must be forced after header edits because the existing
Makefile does not track header dependencies.

To remove autostart, delete `~/.config/autostart/g13-control.desktop`. Quit from
the tray menu. To restore previous bindings, copy the four files from a backup
folder into `~/.g13/`, then run `systemctl --user restart g13-driver.service`.

## Complete game-profile collection

The local library now also includes every XML file from
[cheshire137/logitech-g13-profiles](https://github.com/cheshire137/logitech-g13-profiles):
At source revision `5afe1913d006cc31d54679ed915b36082306cbb0`, 73 files are
represented by 79 profiles including populated source-mode variants. Future
imports follow the upstream default branch, so these counts may change.
Search by game name in **Configure G13 buttons…**, preview the assignments,
choose M1–M4 or Skip for each source mode, then review and apply.

The import converts keystrokes, modifiers and supported multikey sequences. Mouse
functions and other unsupported commands are reported explicitly in the preview.
Age of Empires III is listed, but its source XML contains no G13 assignments, so
it requires manual configuration. Source scripts are never imported or executed.

Refresh the complete collection and install it with:

```bash
/usr/bin/python3 tools/import_game_profiles.py
./scripts/install-g13-tray
```

Restart the tray afterwards. The importer downloads the public repository to a
temporary directory, records its revision and writes `data/g13-games.json`.
The installer copies this generated collection locally; repeated imports replace
that collection without duplicating entries or changing saved mode assignments.
The original smaller atlas remains available alongside it.

## Antigravity credentials

**Credentials → Antigravity credentials…** provides a masked API-key field with
Save and Remove. It is stored as `ANTIGRAVITY_API_KEY` in the same owner-only
configuration file as the other keys. Connection checking is disabled because
no supported Antigravity usage endpoint has been verified. Saving the key does
not enable automatic quota statistics; the Antigravity text-file screen remains
available. The key is not sent to another provider or an unverified endpoint.

## M1 rolling averages and disk activity

M1 now alternates a single `R<speed>` / `W<speed>` after ROOT percentage and temperature. All M1 numbers use a rolling average (five seconds by default). Set **Sample every (seconds)** and **Rolling average (seconds)** on M1, then Save & apply. Both range from 1–60 seconds; the window must be at least the sampling interval. Sampling defaults to one second. THR becomes the rounded mean of sampled active-thread counts. Missing readings remain `n/a`; the window refills after a mode change. API refresh remains 60 seconds.

## Four screens per mode and brightness

Each M tab now contains L1–L4 screen tabs. The four existing screens migrate to M1/L1–L4; other modes begin as editable custom-text labels. Save & apply enables the new layout. The driver remembers each mode’s selected screen until restart. The round left LCD button (BD) adjusts global brightness: hold for 0.4 seconds, then sweep up/down at 20 percentage points per second. Release to keep the level, saved to `~/.g13/brightness`. Screen colours retain their hue while scaling with this brightness. The right round button retains its hardware backlight toggle.

For the existing four-provider setup, M1/L1–L4 show System stats, Steam, Codex local and Discord respectively. The M2–M4 key profiles remain independent; their screen sets can be configured separately.
