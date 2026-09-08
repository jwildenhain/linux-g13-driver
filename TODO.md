# G13 Control follow-up

Status: AWAITING USER APPROVAL (requested 2026-09-08).
Do not implement these changes until the user approves this plan.

- [ ] Diagnose scrambled characters on M2–M4. Inspect cached text, command parsing,
      font indexing and LCD rendering; reproduce with deterministic ASCII fixtures.
      Preserve M1's working system stats. Verify page switching and display clearing.
- [ ] Add a tray-menu item, “Configure G13 buttons…”, that opens a popup showing
      the physical G13 layout with clickable buttons and current assignments.
      Reuse the existing button geometry/image and keymap atlas assets where useful.
- [ ] Add a searchable existing-profile selector using the local keymap collection
      (`data/g13-keymaps.db` / JSON and `tools/build_keymap_db.py`). Show source,
      assignments, and unsupported mappings before importing. Resolve zero-based
      property indices versus printed G1–G22 labels. Do not silently drop macros.
- [ ] Allow editing and saving assignments to M1, M2, M3, or M4/MR. Back up settings
      before applying; preserve M1 system stats and each target's screen/colour.
      Keep physical mode buttons reserved for selecting the four modes.
- [ ] Add credential menu items for Steam, Discord, OpenAI organisation admin and
      Claude organisation admin keys. Each opens a masked dialog with save/remove
      and a read-only connection check. Keep credentials out of Git and logs.
      Explain required IDs/permissions and API-versus-subscription usage clearly.
      Keep Antigravity's local text-file setup until a supported API is verified.
- [ ] Verify popup interactions, profile import/conversion, per-mode saves, secret
      redaction and deterministic LCD output. Perform a physical-device check of
      M2–M4 readability with the user before declaring the display issue resolved.

Approval requested: approve the plan above, or specify changes.

## Current checkpoint: 1.1.0

The tray app, mode profiles and integration providers are implemented. M1 looks
correct according to the user; M2–M4 show scrambled characters on their device.
The follow-up fixes and popup/profile-import UI are not part of this checkpoint.
