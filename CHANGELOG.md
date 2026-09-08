# Changelog

## 1.2.0 — 2026-09-08

- Alternate ROOT read/write speeds and average every M1 metric over a configurable
  rolling window (default five seconds); add separate sampling and averaging controls.
- Show active logical threads (>5% usage) on M1’s CPU row, PSU total watts on
  its memory row, and NIC temperature after network speed.
- Add GPU VRAM percentage to the M1 GPU row alongside utilisation and temperature; preserve available measurements when others are missing.

- Restore all 285 game-library joystick/thumb assignments by translating XML
  control identifiers; recognise PERIOD as Linux KEY_DOT.
- Rewrite the README with actual GTK screenshots, complete usage/setup guidance,
  integration limits, troubleshooting and reproducible isolated screenshot capture.

- Add a switch between physical control labels and configured assignments.
- Add per-mode editing of four joystick directions and two thumb buttons, with
  keyboard-mode activation explicitly included in the review summary.

- Group game source modes into one entry with per-mode destinations and Skip.
- Add current/proposed key previews, duplicate/overlap information, and a batch
  review dialog with conflict detection, shared backups and rollback.
- Audit 96 source modes across 82 groups; keep source snapshots distinct from
  actual saved G13 modes. No redundant profiles are removed automatically.

- Fix scrambled lowercase LCD text caused by a backslash comment removing a
  glyph during preprocessing. Add font-size and pixel-level regression checks.
- Add a clickable G13 keypad popup, searchable profile selection and saved-mode
  copying. Save assignments to one mode while preserving screens and colours.
- Import the complete cheshire137 game library: 73 XML files, 79 mode profiles.
  Convert supported keys, modifiers and multikey sequences; report unsupported
  actions and profiles without G13 assignments.
- Add masked Steam, Discord, OpenAI and Claude credential dialogs with independent
  save/remove and read-only connection checks.
- Add masked Antigravity key storage. Usage API checks remain unavailable.
- Validate configuration isolation, XML conversion and real GTK interactions.

Physical confirmation of the LCD fix and live authenticated API checks remain
pending. Game-library data and credentials are not included in the source commit.

## 1.1.0 — 2026-09-08

- Add native GTK/Ayatana tray settings and desktop login autostart.
- Add opt-in M1/M2/M3/MR profiles, per-screen lighting and G1–G22 key/macro choices.
- Preserve built-in system statistics on M1; add cached integration providers.
- Add configuration backups, validation and driver/provider regression tests.
- Include the existing service management, LCD and keymap-tool source work.
- Known issue: user reports scrambled characters on M2–M4. Physical readability
  is not yet verified; the follow-up fix and verification status are recorded in TODO.md.
