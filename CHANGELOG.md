# CHANGELOG

This file tracks project changes and implementation notes so the final report can describe what was built, when it was added, and why it mattered.

## 2026-04-29

### Added

- Created `CHANGELOG.md` to keep a running, report-ready record of project work across the controller, light node, and alarm node.

### Documented Baseline

- Audited `plan.md`, `Midterm Project Presentation.pptx`, `README.md`, and the current `controller/` code.
- Confirmed the repo currently contains a customized `controller/` app and a copied-but-unmodified `light_ctrl/` sample; the planned `alarm-node/` app and shared `common/` module are not present yet.
- Confirmed the current controller already sends fixed `HOME`, `AWAY`, `NIGHT`, and `CLEAR ALERT` actions, but it does not yet implement the planned `Alert` Generic OnOff Server behavior from `plan.md`.

### Clarified Architecture

- Compared the proposal slides against `plan.md` and confirmed `plan.md` is the implementation source of truth for v1.
- Documented that the earlier slide proposal used Scene-based control and a sensor sample for Board 3, but the current plan intentionally simplifies this to four fixed Generic OnOff channels: `Home`, `Away`, `Night`, and `Alert`.
- Audited `light_ctrl/` and confirmed it is still the Nordic `light_ctrl` NLC sample with Lightness, Scene, Sensor, and Light LC models, so it will need a substantial rewrite to become the project’s light node.
- Identified the light-node work scope as replacing the current `light_ctrl` sample behavior with four Generic OnOff Servers and custom LED patterns for `Home`, `Away`, `Night`, and `Alert`.

### Implemented Light Node

- Switched the light-board work to the `light/` app, which is the correct Nordic `light` sample base for the planned v1 light node.
- Replaced the stock `light/src/model_handler.c` behavior that treated each Generic OnOff Server as an independent LED with project-specific shared state for `HOME`, `AWAY`, `NIGHT`, and `ALERT`.
- Added light-node mode handling so `Home`, `Away`, and `Night` mesh messages update one shared `current_mode` instead of four unrelated LED states.
- Added alert handling so the `Alert` mesh channel drives a global flashing pattern across all LEDs until `Alert OFF` is received.
- Added UART logs for `MODE: ...` and `ALERT: ...` state changes, plus default boot logs for `HOME` and cleared alert state.
- Updated `light/prj.conf` device strings so provisioning shows this board as `Smart Home Light Node` instead of the generic sample name.

### Repo Maintenance

- Converted `light/` from a gitlink-style entry in the parent repository index into a normal tracked folder so the project uses only the main `smart-home-safety-system` repo and not a nested submodule-like entry for the light node.

### Added Laptop Speaker Alarm Bridge

- Added `tools/laptop_alarm_bridge.py` to connect board UART logs to laptop audio alarm playback.
- Bridge behavior:
  - Detects `ALERT: ACTIVE` in UART and starts repeating alarm sound on macOS using `afplay`.
  - Detects `ALERT: CLEAR` and stops the alarm sound.
- Added CLI options for serial port, baud rate, custom sound file, and trigger cooldown.
- This enables a higher-impact demo without extra hardware by using the laptop speaker as the siren output.

### Run Laptop Alarm Bridge

- Install dependency:
  - `pip install pyserial`
- Find serial port:
  - `ls /dev/cu.usbmodem*`
- Run:
  - `python3 tools/laptop_alarm_bridge.py --port /dev/cu.usbmodemXXXX --baud 115200`
- Optional custom sound:
  - `python3 tools/laptop_alarm_bridge.py --port /dev/cu.usbmodemXXXX --sound /System/Library/Sounds/Glass.aiff`

### Removed Controller Password Gate

- Removed UART password authorization logic from `controller/src/model_handler.c`.
- `Button 3` (`CLEAR ALERT`) now works immediately again without entering a password.
- Removed controller console getchar settings from `controller/prj.conf` that were only needed for password input.
