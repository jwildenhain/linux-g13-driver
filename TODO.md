# G13 Control implementation checklist

Approved on 2026-09-08. Implementation and automated checks are complete.

- [x] Fix scrambled lowercase text on M2–M4. A trailing backslash in a font-table
      comment removed the next glyph row during preprocessing. Add a compile-time
      table-size check and pixel-level rendering/clearing regression tests.
- [x] Add a clickable G13 keypad popup with G1–G22 assignment editing.
- [x] Add searchable local profiles and saved-mode copying, with previews and
      explicit notes for unsupported assignments.
- [x] Save selected assignments to M1–M4 with backups, preserving screen content,
      lighting, joystick assignments and other modes.
- [x] Add masked Steam, Discord, OpenAI and Claude credential dialogs with
      save/remove and read-only connection checks.
- [x] Add masked Antigravity key storage; leave connection checks disabled until
      a supported usage endpoint is verified.
- [x] Import all 73 XML files from cheshire137/logitech-g13-profiles as 79 mode
      profiles. Include the empty Age of Empires III profile with an explanation.
- [x] Test XML conversion, symbolic keys, combinations, macros, target-mode
      isolation, credential storage and real GTK interactions.

## Remaining verification and limitations

- [ ] User confirms M2–M4 readability and backlight behaviour on the physical G13.
- [ ] Verify authenticated stats with user-provided service credentials.
- [ ] Connect Antigravity usage only if a supported endpoint becomes available.

Unsupported imported actions retain their target assignments and are reported in
the popup. The generated game datasets remain local; the importer and installation
instructions are tracked so another checkout can obtain the same collection.

## Git checkpoint

The pushed 1.1.0 checkpoint is commit `00afdf8`. Version 1.2.0 contains the
font fix, grouped keypad editor, complete game import, credential dialogs and
configurable rolling system statistics. See [the changelog](CHANGELOG.md) and [usage guide](docs/TRAY.md).

## Grouped assignment redesign

- [x] Audit source-mode groupings and exact/partial assignment matches.
- [x] Group games, with independent M1–M4/Skip destinations for each source mode.
- [x] Preview current and proposed assignments and show source duplicate details.
- [x] Review and apply multiple modes with one backup and rollback on write failure.
- [x] Verify single-mode, three-mode, destination-conflict, review cancel/apply,
      duplicate-classification, preflight and rollback paths.

Audit findings: [PROFILE_AUDIT.md](docs/PROFILE_AUDIT.md).

## Assignment labels and auxiliary controls

- [x] Switch the G13 drawing between physical labels and assigned keys/macros.
- [x] Add joystick direction controls plus left/below thumb buttons.
- [x] Save all six per mode; disclose keyboard-mode activation for directions.
- [x] Verify label switching, imports, persistence and driver press/release events.

## Auxiliary import review and documentation

- [x] Audit every game for joystick/thumb assignments and document the per-game results.
- [x] Translate XML auxiliary identifiers and PERIOD; verify all 285 assignments.
- [x] Add regression coverage for source-to-driver auxiliary numbering.
- [x] Rewrite README with actual UI screenshots and complete functionality/setup guidance.

## M1 statistics and 1.2.0 verification

- [x] Add GPU VRAM percentage, active logical threads and PSU total power.
- [x] Move NIC temperature to NET and alternate ROOT read/write speeds.
- [x] Add configurable sample interval and rolling average (defaults: 1s / 5s).
- [x] Validate average expiry, missing readings, GPU CSV, active-thread threshold,
      PSU units, disk alternation and cached frames with driver regression tests.
- [x] Pass all 21 Python tests and the isolated GTK interaction check.
- [x] Refresh README screenshots and include Steam API-key setup instructions.
- [x] Synchronise VERSION and Java build metadata at 1.2.0.

## Independent LCD screens and brightness

- [x] Add four screen slots per M mode with independent source/colour settings.
- [x] Migrate the four existing screens to M1/L1–L4 and retain mode assignments.
- [x] Separate LCD selectors from mode selectors and remember the selected page.
- [x] Add hold-to-sweep brightness and persistent release level.
- [ ] Confirm BD button identification, sweep feel and right-button toggle on hardware.

## 1.3.0 checkpoint

- [x] Document independent M/L selection, existing-screen migration to M1 and saved brightness.
- [x] Update the settings screenshot for the L1–L4 tabs.
- [x] Synchronise VERSION and Java build metadata at 1.3.0.
