# Auxiliary game-assignment review

Reviewed source revision `5afe1913d006cc31d54679ed915b36082306cbb0` of [cheshire137/logitech-g13-profiles](https://github.com/cheshire137/logitech-g13-profiles).

64 XML files / 69 populated source modes contain 285 assignments for the six requested joystick/thumb controls.
Counts use unique control assignments per imported source mode, excluding backup entries.

## Finding and correction: XML identifier translation

The UI and driver supported these controls, but the XML importer retained G23–G29 while the profile converter expected canonical names. This caused the assignments to be skipped. The importer now translates them before conversion and retains the original XML identifier for traceability. Saved device bindings change only when a profile is reviewed and applied.

| XML identifier | Control | Canonical name | Driver property | Assignments |
| --- | --- | --- | --- | --- |
| G23 | Thumb left | LEFT | G33 | 55 |
| G24 | Thumb below | DOWN | G34 | 38 |
| G26 | Stick up | STICK_UP | G36 | 54 |
| G27 | Stick right | STICK_RIGHT | G38 | 43 |
| G28 | Stick down | STICK_DOWN | G39 | 47 |
| G29 | Stick left | STICK_LEFT | G37 | 48 |

The translation is corroborated by [neoresin’s XML converter mapping](https://github.com/neoresin/g13xml2keybinds/blob/master/translate.GButton2Direction.list).

All 285 assignments now have supported key/macro actions. Going Medieval’s Stick down action uses PERIOD; the importer now recognises it as Linux KEY_DOT.

There are also five G25 assignments. The reference converter calls this control TOP (driver G35); it is outside the six controls just added and needs separate treatment.

## Validation

Regenerated the local collection and verified all 285 conversions. A regression test covers all seven XML identifiers G23–G29, the six supported driver inputs, the retained TOP warning, original source labels and PERIOD conversion. Existing saved assignments remain unchanged until the user applies a game profile.

The full game collection still contains one unsupported mouse-function action in Dolphin Wii/GameCube Emulator, separate from these auxiliary controls.

## Per-profile assignments

A dash means this source mode does not specify that control. Names below are the source author’s action labels.

| Source profile/mode | Thumb left | Thumb below | Stick up | Stick right | Stick down | Stick left |
| --- | --- | --- | --- | --- | --- | --- |
| ANNO 1800 | Space World Map | — | K Storage | — | — | — |
| Against the Storm | Z Blightrot overlay | — | — | — | — | — |
| Astroneer | — | — | — | — | — | G Emote wheel |
| Baldur's Gate 3 | M Map | P Inspiration | V Shove | ] Next char | ` Highlight characters | [ Prev char |
| Banished | — | — | Insert Zoom in | — | Delete Zoom out | — |
| Bear and Breakfast · source M1 | M Map | — | — | — | — | — |
| Before We Leave | — | — | Page Down | — | Page Up | — |
| Borderlands 2 | M Map | F4 Mail | I Inventory | ] Next mission | X Sell all junk | [ Prev mission |
| Borderlands 3 | M Map | Z Quick Menu | I Inventory | — | — | I Inventory |
| Borderlands | M Map | H Horn | I Inventory | Page Up | — | Page Down |
| Breathedge | — | — | 1 | 3 | 4 | 2 |
| Civilization V | G Hex Grid | — | Page Up Zoom | — | Page Down Zoom | — |
| Control | Tab Map | — | — | — | — | — |
| Coral Island | M Map | Z Zoom | — | — | — | — |
| Cyberpunk 2077 | M Map | N Photo mode | I Main menu | — | K Crafting | J Journal |
| Dawn of Man | 9 Structures | 7 Tasks | R Zoom | Page Down Look | F Zoom | Page Up Look |
| Default Profile · source M1 | — | — | B | — | — | B |
| Default Profile · source M2 | 6 | 7 | W | D | S | A |
| Default Profile · source M3 | 6 | 7 | W | D | S | A |
| Dinkum | M Map | — | — | — | — | — |
| Divinity Original Sin 2 | M Map | Home Center Camera | — | — | — | — |
| Dolphin Wii/GameCube Emulator · source M1 | — | Home | Up | Right | Down | Left |
| Dolphin Wii/GameCube Emulator · source M2 | Z | — | C-Up | C-Right | C-Down | Left |
| Dragon Age 2 | M Map | 0 | 7 | 8 | 9 | P Abilities |
| Dragon Age Inquisition | M Map | 0 Potion 1 | Slot 1 | Slot 3 | Slot 4 | Slot 2 |
| Fallout 4 | M Map | X | F Favorites | Right | Z Sort | Left |
| Flotsam | — | — | — | X Inc Buoy Rad | — | Z Dec Buoy Rad |
| Foundation | — | Ctrl + U Toggle UI | R Tilt camera | Page Down Zoom | F Tilt camera | Page Up Zoom |
| Frostpunk | Home Map | — | Page Up Zoom | ] Select Next | Page Down Zoom | [ Select Previous |
| Garden Story | M Map | — | — | D Page Right | — | S Page Left |
| Going Medieval | — | — | , Toggle Terrain Up | K Toggle Rooms | . Toggle Terrain Down (unsupported: Unconvertible . Toggle Terrain Down) | I Toggle Roofs |
| Graveyard Keeper | M Map | — | 1 Quickslot | 3 Quickslot | 4 Quickslot | 2 Quickslot |
| High on Life | — | — | 1 Kenny | 3 Sweezy | 4 Creature | 2 Gus |
| Humankind | — | — | Page Up | — | Page Down | — |
| It Lurks Below | M Minimap | X Dig Toggle | 1 | 3 | 4 | 2 |
| Kingdoms and Castles | — | — | V Zoom in | — | F Zoom out | — |
| Lost Ark | M Map | K Combat Skills | J Quests | — | Y Emote | 5 Item |
| Mass Effect 2 | M Map | C Rally | 1 | 3 | 4 | 2 |
| Mass Effect 3 | V Nav assist | C Rally | — | — | — | — |
| Mass Effect Andromeda | M Map | Q Objective | P Profiles | O Codex | U Skills | I Inventory |
| Mass Effect | M Map | C Rally | 1 | 3 | 4 | 2 |
| My Time at Portia | M Map | — | F Relic Scanner | — | — | — |
| Northgard | T Minimap display type | I World info | — | — | — | — |
| Overwatch 2 · source M1 | 7 | 8 | G Hello | 3 Acknowledge | Z Ult Status | B Thanks |
| Overwatch 2 · source M2 | 7-6 Voice Lines | 9-8 Voice Lines | G Hello | 3 Acknowledge | Z Ult Status | B Thanks |
| Overwatch 2 · source M3 | 6 | 7 | W | D | S | A |
| Overwatch | Up voice -> Right voice | Left voice => Down voice | G | 3 | 2 | B |
| Oxygen Not Included | — | — | 1 | 3 | 4 | 2 |
| Pathfinder Wrath of the Righteous | M Map | — | 1 | 3 | 4 | 2 |
| Patron | M Map | H Townhall camera | Home Look up | O Annual | End Look down | V Residents |
| Pentiment | M Map | 5 | 1 | 3 | 4 | 2 |
| Pillars of Eternity II: Deadfire | M Map | — | = Next Row | — | - Prev Row | — |
| Pillars of Eternity | M Map | F Formations | = Zoom | ' Next Menu | - Zoom | ; Prev Menu |
| Project 64 | — | — | D-Up | D-Right | D-Down | Left |
| Skyrim | M Map | L Local Map | Q Favorites | 4 | 5 | 3 |
| Slay the Spire | M Map | — | — | — | — | — |
| Stardew Valley | M | — | — | — | — | — |
| The Outer Worlds | M | — | J Journal | , Comp Menu | — | K Char Menu |
| The Sims 2 | C Snapshot | — | Page Up Floor | Home Wall Up | Page Down Floor | End Wall Down |
| The Sims 3 | M Map | C Snapshot | Page Up Floor | Home Wall Up | Page Down Floor | End Wall Down |
| The Sims 4 | M Map | C Snapshot | Page Up Floor | Home Wall Up | Page Down Floor | End Wall Down |
| The Universim | M Quest Log | F4 Toggle HUD | F1 Planet Filters | F3 Building Panel | — | F2 Nugget Panel |
| The Witcher 3 | M Map | V Change Objective | — | — | — | — |
| Tiny Tina's Wonderlands | M Map | J Myth Rank | I Inventory | ] Next quest | 2 Weapon | [ Prev quest |
| Tropico 6 | Space Archipelago | — | — | — | — | — |
| Two Point Campus | 5 Inbox | 5 Inbox | Up Zoom | F Pitch | Down Zoom | R Pitch |
| Two Point Hospital | 5 Staff overview | — | Up | F | Right | R |
| Tyranny | / Area Map | ' World Map | Q Zoom | — | E Zoom | — |
| Urbek City Builder | M Minimap | U Toggle UI | X Zoom | PgDwn Tilt Up | Z Zoom | PgUp Tilt Down |
