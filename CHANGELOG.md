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

### Added Visual Command Center

- Added a new responsive browser dashboard in `dashboard/` branded as `MeshGuard Command Center` for laptop and phone demos.
- Implemented a cinematic control-room UI with a live mode banner, animated room floorplan, node vitals, incident panel, and scrolling event timeline.
- Added browser-side audio integration so alert and Night-mode sounds are triggered directly from the dashboard after the user enables audio.
- Added `tools/meshguard_command_center.py`, a zero-extra-dependency Python server that serves the dashboard, streams live state over Server-Sent Events, and reads UART from the three boards using built-in macOS tools.
- Added optional desktop speaker playback through `afplay` so the laptop can blare the alert loop even if the dashboard is being viewed from a phone.
- Reused the existing repo sound assets for the live demo instead of introducing external media dependencies.
- Updated the root `README.md` with quick-start instructions for both dashboard demo mode and live three-board mode.

### Hardened Visual Command Center

- Added `--list-ports` to `tools/meshguard_command_center.py` so the team can identify `/dev/cu.usbmodem*` ports before starting the live dashboard.
- Fixed command-center shutdown so `Ctrl-C` can stop the HTTP server without blocking in the signal handler.
- Improved UART startup diagnostics so bad or busy serial ports print a useful error instead of failing silently in a background thread.
- Renamed the demo thread stop flag to avoid shadowing Python `Thread` internals.
- Added HTTP `HEAD` support for dashboard, API, and media routes so quick health checks do not report false endpoint failures.
- Suppressed expected browser/SSE disconnect tracebacks so the demo console stays clean when phones or verification tools disconnect.
- Added sound-file existence checks before the command center starts.
- Fixed Night-mode audio triggering so the bedtime sound plays once per mode transition instead of once per board log.
- Improved browser dashboard behavior when the event stream is unavailable and when browser audio playback is blocked.
- Added `DEMO.md` with a full step-by-step presentation script for the real boards, laptop dashboard, phone display, and backup demo mode.

### Added Distributed Laptop Demo Mode

- Added `/api/ingest` to `tools/meshguard_command_center.py` so remote laptops can forward UART logs into the main visual dashboard over Wi-Fi.
- Added optional `--ingest-token` support for the command center and matching `--token` support for remote UART agents.
- Added `--remote-only` so the main dashboard can run even when no board is plugged into that laptop.
- Added `tools/meshguard_uart_agent.py`, a zero-extra-dependency UART forwarder for the controller, light, or alarm laptop.
- Added local and remote UART heartbeats so dashboard node status stays online during quiet periods between board log messages.
- Updated the UART agent so `--command-center` accepts either the base dashboard URL or the full `/api/ingest` endpoint printed by the command center.
- Hardened UART decoding in both the command center and remote agent so non-UTF8 serial bytes are replaced instead of crashing the process.
- Added README troubleshooting notes for busy UART ports and dual `/dev/cu.usbmodem...` board interfaces.
- Updated `README.md` and `DEMO.md` with commands for the three-laptop setup where each laptop owns one board.

### Recovered Light Build Directory

- Diagnosed the `light/build` failure where Ninja depended on `../../.git/index`, which pointed at the old nested `light/.git/index` path after `light/` was converted from a gitlink-style folder into a normal project folder.
- Regenerated `light/build` with a pristine build so `zephyr/include/generated/app_commit.h` now depends on the parent repository `.git/index`.
- Verified the light app builds successfully for `nrf54l15dk/nrf54l15/cpuapp` and produces `light/build/merged.hex`.

### Repo Maintenance

- Converted `light/` from a gitlink-style entry in the parent repository index into a normal tracked folder so the project uses only the main `smart-home-safety-system` repo and not a nested submodule-like entry for the light node.

### Added Laptop Speaker Alarm Bridge

- Added `tools/laptop_alarm_bridge.py` to connect board UART logs to laptop audio alarm playback.
- Bridge behavior:
  - Detects `ALERT: ACTIVE` in UART and starts repeating alarm sound on macOS using `afplay`.
  - Detects `ALERT: CLEAR` and stops the alarm sound.
- Extended the bridge to detect `MODE: NIGHT` and play `goodnight_sound.mp3` once for a bedtime-style effect.
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
