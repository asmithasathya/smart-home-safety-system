# Smart Home Safety System

This repo contains a three-board Bluetooth Mesh smart home safety demo built on the Nordic `nRF54L15 DK`. Each board is flashed separately, each board has a different role, and all three work together on the same mesh network:

- `firmware/controller/` - Entryway Controller
- `firmware/light/` - Living Room Light Node
- `firmware/alarm/` - Bedroom Alarm Node
- `host/` - optional laptop-side UART audio bridge
- `docs/` - supporting report material

Related project docs:

- [intro.md](intro.md)
- [docs/UPDATES.md](docs/UPDATES.md)

## A. Introduction

### Problem statement

The project demonstrates a small smart-home safety system where multiple wireless embedded nodes must stay synchronized without direct wiring between them. One node controls the overall home state, one node visually reflects that state, and one node behaves like an alarm subsystem that can be armed, triggered, and cleared.

### Target application

The target use case is a dorm room, apartment, or small home prototype where:

- the user selects `Home`, `Away`, or `Night` at the entry point
- lighting/status indicators reflect the system state
- an intrusion event can trigger a shared alert
- clearing the alert requires both a clear request and password confirmation

### High-level architecture

The system uses four shared Bluetooth Mesh group channels:

- `Home`
- `Away`
- `Night`
- `Alert`

Board responsibilities:

1. `Board 1` (`firmware/controller/`) sends fixed mesh commands for `HOME`, `AWAY`, `NIGHT`, and `CLEAR ALERT`.
2. `Board 2` (`firmware/light/`) subscribes to those mesh messages and updates LED patterns to reflect the current apartment state.
3. `Board 3` (`firmware/alarm/`) subscribes to the same mode messages, arms in `Away` and `Night`, and publishes `Alert ON` if an intrusion is triggered while armed.
4. The optional host script (`host/laptop_alarm_bridge.py`) listens to board UART logs and plays sounds on a laptop speaker.

### Key features

- Three separately flashable Zephyr/Nordic firmware applications
- Bluetooth Mesh coordination across three `nRF54L15 DK` boards
- Fixed controller actions for `HOME`, `AWAY`, `NIGHT`, and `CLEAR ALERT`
- Visual mode indication on the controller and light node
- Intrusion simulation on the alarm board using a built-in button
- Password-confirmed alert clearing through the controller UART
- Optional laptop speaker playback for alarm and Night-mode sound effects

### Performance summary

No formal measured values for latency, range, energy, or battery runtime are included in this repo.

What is verified in this project:

- all three firmware apps build successfully
- each board can be flashed independently
- all three boards can be provisioned into one mesh
- controller mode changes propagate to the light and alarm boards
- the alarm board can publish global alert events
- the alert clear flow requires password confirmation on the controller UART

Methods for reproducing latency and range measurements are included later in this README, but no official benchmark numbers are claimed.

## B. Hardware details

### Boards used and MCU details

The project uses:

- `3 x Nordic nRF54L15 DK`

Assigned roles:

- Board 1 -> `Entryway Controller`
- Board 2 -> `Living Room Light Node`
- Board 3 -> `Bedroom Alarm Node`

The `nRF54L15` SoC provides:

- `128 MHz Arm Cortex-M33`
- `128 MHz RISC-V coprocessor`
- `1.5 MB NVM`
- `256 KB RAM`
- `2.4 GHz` multiprotocol radio

Official references:

- nRF54L15 DK overview: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-DK
- nRF54L15 SoC page: https://www.nordicsemi.com/Products/nRF54L15

### Additional peripherals

No external electronic peripherals were used.

Only these supporting items were used:

- `USB-C` data cables
- laptops for flashing, UART logging, and optionally running the host script

No external sensors, speakers, buzzers, relays, batteries, or custom modules were added.

### Hardware modifications

No hardware modification was required.

- no jumper rework
- no bodge wires
- no custom PCB
- no enclosure
- no soldering changes for the normal demo flow

Because the final project uses stock dev kits only, there are no project-specific custom schematics or assembly photos in the repo. For official schematics, layout, and board documentation, use Nordic's hardware files bundle:

- Hardware files page: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-DK/Hardware-files
- Hardware bundle: https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/nrf54l15-dk/pca10156-nrf54l15-dk-1_0_0.zip

### Power subsystem

The system was powered entirely over USB from laptops.

- power source: laptop USB-C port
- cable type: USB-C data cable
- battery: none
- charging approach: not applicable
- estimated runtime: not applicable, because the project was not battery-powered

### RF details

RF use in this project:

- band: `2.4 GHz`
- protocol used by the project: `Bluetooth Mesh`
- antenna used: on-board DK antenna
- external RF connector: available on the board as `SWF`, but not used

Nordic SoC RF specifications referenced for documentation:

- maximum TX power: `+8 dBm (CSP) / +7 dBm (QFN)`
- RX sensitivity: `-96 dBm (1M Bluetooth LE)`

Expected range:

- not formally measured
- depends on room layout, walls, people, and interference
- should be treated as a classroom/lab prototype rather than a tuned production RF design

Compliance note:

- this is a prototype on development hardware
- the repo does not claim end-product RF certification or consumer-product compliance

## C. Software environment

### Firmware

#### IDE/toolchain and versions

The project is intended to be built in a Nordic `nRF Connect SDK` environment.

Verified versions from the current build environment:

- `nRF Connect SDK v3.2.1`
- `Zephyr v4.2.99`
- `west 1.4.0`
- `CMake 3.21.0`
- `Zephyr SDK 0.17.0`
- `arm-zephyr-eabi-gcc 12.2.0`
- `Python 3.12.4` in the Nordic toolchain

Supported developer workflows:

- `nRF Connect for VS Code`
- `nRF Connect for Desktop`
- plain terminal use with `west`

#### SDK/RTOS/compiler summary

- SDK: `nRF Connect SDK 3.2.1`
- RTOS: `Zephyr 4.2.99`
- build system: `west` + `CMake` + `Ninja`
- compiler: `GNU Arm Embedded toolchain through Zephyr SDK`

#### Build system and board configuration

All three firmware apps are built for:

```bash
nrf54l15dk/nrf54l15/cpuapp
```

Each firmware folder contains a normal Zephyr app plus board-specific config files. The project also uses `sysbuild`, which builds the application and radio child image together.

### Other software

#### Host-side software

The optional laptop audio bridge uses:

- language: `Python 3`
- dependency file: `host/requirements.txt`
- dependency: `pyserial>=3.5,<4`

#### OS compatibility

Firmware build/flash:

- depends on standard Nordic `nRF Connect SDK` support

Host audio bridge:

- currently designed for `macOS`
- uses `afplay` for audio playback

UART examples in this README use `screen` on macOS. Equivalent serial tools can be substituted on other operating systems.

### Programming/debugging tools

The project uses:

- on-board `SEGGER J-Link OB`
- `west flash`
- USB virtual serial ports for UART logging
- `nRF Mesh` mobile app for provisioning and model configuration

### Radio stack and protocol configuration

This project uses the Bluetooth Mesh support provided by Nordic/Zephyr.

Key application-level configuration:

- Bluetooth Mesh enabled
- `Generic OnOff Client` models on the controller
- `Generic OnOff Server` models on the light and alarm boards
- `Generic OnOff Client` on the alarm board for `Alert ON` publish
- `Relay` enabled
- `Friend` enabled
- `GATT Proxy` enabled
- provisioning via `PB-GATT`

This repo does not implement custom PHY tuning, custom RF channels, or proprietary 2 Mbps/4 Mbps application data paths. It relies on the standard Bluetooth LE and Bluetooth Mesh stack behavior from the SDK.

## D. Reproducibility guide

### 1. Hardware setup

No custom assembly is required.

1. Take three `nRF54L15 DK` boards.
2. Connect each board to a laptop with a USB-C data cable.
3. Assign one board to each firmware image:
   - controller
   - light
   - alarm

No inter-board wiring is needed.

### 2. Built-in button and LED map

#### Controller board

- `Button 0` -> send `HOME`
- `Button 1` -> send `AWAY`
- `Button 2` -> send `NIGHT`
- `Button 3` -> request `CLEAR ALERT`

- `LED 0` -> current controller mode is `Home`
- `LED 1` -> current controller mode is `Away`
- `LED 2` -> current controller mode is `Night`
- `LED 3` -> short feedback blink for clear-alert request

#### Light board

- `HOME` -> `LED 0`
- `AWAY` -> `LED 1`
- `NIGHT` -> `LED 2 + LED 3`
- `ALERT` -> all LEDs flash

#### Alarm board

- `Button 0` -> simulate intrusion

- `HOME` -> `LED 0`
- `AWAY` -> `LED 1`
- `NIGHT` -> `LED 2 + LED 3`
- `ALERT` -> all LEDs flash

### 3. Environment setup

Use an `nRF Connect SDK` terminal where `west` is already available.

From the repo root:

```bash
cd /Users/asmitha/embedded-sys/smart-home-safety-system
```

Optional host-script setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r host/requirements.txt
```

### 4. Build instructions

Build controller:

```bash
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/controller firmware/controller
```

Build light node:

```bash
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/light firmware/light
```

Build alarm node:

```bash
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/alarm firmware/alarm
```

Expected result:

- each build completes successfully
- each build directory contains a `merged.hex`

### 5. Flashing and programming

Flash each board from the matching build directory:

```bash
west flash --build-dir build/controller
west flash --build-dir build/light
west flash --build-dir build/alarm
```

Best practice:

- flash one target board at a time to avoid confusion

### 6. UART logging

Find serial devices:

```bash
ls /dev/cu.usbmodem*
```

Open a UART terminal:

```bash
screen /dev/cu.usbmodemXXXX 115200
```

Expected boot logs:

- controller: `Bluetooth initialized`, `Mesh initialized`, password prompt
- light: `Bluetooth initialized`, `Mesh initialized`, `MODE: HOME`, `ALERT: CLEARED`
- alarm: `Bluetooth initialized`, `Mesh initialized`, `MODE: HOME (disarmed)`, `ALERT: CLEAR`

### 7. Provisioning and mesh setup

Use the `nRF Mesh` mobile app.

1. Create a mesh network such as `SmartHomeSafety`.
2. Provision all three boards using `No OOB`.
3. Rename the nodes after provisioning:
   - `Entryway Controller`
   - `Living Room Light Node`
   - `Bedroom Alarm Node`
4. Create the groups:
   - `Home`
   - `Away`
   - `Night`
   - `Alert`
5. Create one application key, for example `App Key 1`, and add it to each node.
6. Configure the controller publishes:
   - `Element 1` -> `Home`
   - `Element 2` -> `Away`
   - `Element 3` -> `Night`
   - `Element 4` -> `Alert`
7. Bind and subscribe the light node's four `Generic OnOff Server` models to the matching groups.
8. Bind and subscribe the alarm node's four `Generic OnOff Server` models to the matching groups.
9. Configure the alarm node's `Generic OnOff Client` publication to `Alert`.

Advertising names to expect before renaming:

- controller -> `Mesh Light Switch`
- light -> `Smart Home Light Node`
- alarm -> `Mesh Light`

### 8. Running the demo

Recommended startup order:

1. Power all three boards.
2. Open UART logs for the controller and alarm boards.
3. Confirm all boards boot and initialize the mesh stack.
4. Confirm the nodes are already provisioned into the same mesh.
5. Optionally start the host audio bridge.

Optional host bridge:

```bash
python3 host/laptop_alarm_bridge.py --test-sound
python3 host/laptop_alarm_bridge.py --test-night-sound
python3 host/laptop_alarm_bridge.py --port /dev/cu.usbmodemXXXXXXXXXXXX --baud 115200
```

Compatibility launcher:

```bash
python3 tools/laptop_alarm_bridge.py --port /dev/cu.usbmodemXXXXXXXXXXXX --baud 115200
```

The host bridge watches for:

- `ALERT: ACTIVE`
- `ALERT: CLEAR` or `ALERT: CLEARED`
- `MODE: NIGHT (armed)`

For the cleanest demo, connect the host bridge to the `alarm` board UART so the controller UART stays free for password entry.

### 9. Demo verification steps

#### Home mode

1. Press controller `Button 0`.
2. Confirm controller prints `Sending HOME`.
3. Confirm controller shows only `LED 0`.
4. Confirm light node prints `MODE: HOME`.
5. Confirm alarm node prints `MODE: HOME (disarmed)`.

#### Away mode

1. Press controller `Button 1`.
2. Confirm controller prints `Sending AWAY`.
3. Confirm controller shows only `LED 1`.
4. Confirm light node prints `MODE: AWAY`.
5. Confirm alarm node prints `MODE: AWAY (armed)`.

#### Night mode

1. Press controller `Button 2`.
2. Confirm controller prints `Sending NIGHT`.
3. Confirm controller shows only `LED 2`.
4. Confirm light node prints `MODE: NIGHT`.
5. Confirm alarm node prints `MODE: NIGHT (armed)`.
6. If the host bridge is running on the alarm UART, confirm the goodnight sound plays once.

#### Intrusion while disarmed

1. Put the system in `HOME`.
2. Press alarm-board `Button 0`.
3. Confirm alarm node prints `INTRUSION: IGNORED (DISARMED)`.
4. Confirm no global alert starts.

#### Intrusion while armed

1. Put the system in `AWAY` or `NIGHT`.
2. Press alarm-board `Button 0`.
3. Confirm alarm node prints `INTRUSION: DETECTED (ARMED)`.
4. Confirm the light node enters alert flashing state.
5. Confirm the host bridge starts the alarm sound if enabled.

#### Password-confirmed alert clear

1. While the alert is active, press controller `Button 3`.
2. Confirm the controller prints the clear-request message.
3. Confirm the alert stays active.
4. Type the password into the controller UART and press Enter.
5. Default demo password in the current firmware: `1234`
6. Confirm the controller prints `Password accepted: clearing alert`.
7. Confirm the light and alarm boards clear the alert.

### 10. Testing and measurement

No formal measurement dataset is included in the repo. The following methods can be used to reproduce simple evaluation results.

#### Latency

1. Open UART logs on the controller and one remote board.
2. Record a slow-motion video of the button press and remote LED/UART response.
3. Count frames between local action and remote response.
4. Convert frame count to time using the camera frame rate.

#### Range

1. Start with all boards close together and verify correct operation.
2. Move one remote node farther away in the real environment.
3. Repeat `HOME`, `AWAY`, `NIGHT`, and alert tests at each distance.
4. Record the farthest distance where all expected behaviors still occur reliably.

Document the environment:

- room type
- walls or obstacles
- approximate interference level
- board orientation

#### Energy/runtime

No battery-powered runtime or current-consumption results are claimed in this repo. The DK includes power-related hardware support, but it was not used in the final demo.

### 11. Troubleshooting

#### `west: command not found`

Use an `nRF Connect SDK` shell instead of a plain terminal.

#### Serial port does not appear

- try a different USB-C cable
- make sure the cable supports data
- unplug and reconnect the board
- try a different USB port

#### Flashing fails

- disconnect other Nordic boards
- retry with only the target board connected
- make sure the build directory matches the firmware you intend to flash

#### Provisioning does not find the board

- keep the phone close to the board
- use `No OOB`
- check whether the board is already provisioned and therefore no longer advertising as unprovisioned

#### Controller commands do nothing

- confirm the controller was provisioned
- confirm `App Key 1` is added to the node
- confirm each controller client is bound and publishing to the correct group

#### Alarm does not trigger globally

- confirm the alarm board is in `AWAY` or `NIGHT`
- confirm the alarm client's publication is set to `Alert`
- confirm the other nodes subscribe to `Alert`

#### Alert clears without password

- reflash the current controller firmware
- watch the controller UART and confirm the clear request appears before password entry

#### Host bridge is silent

- confirm `pyserial` is installed
- confirm the selected UART port is correct
- confirm no other terminal program is already attached to that port
- confirm the UART stream includes `ALERT: ACTIVE`, `ALERT: CLEAR`, or `MODE: NIGHT (armed)`
- confirm you are using macOS, because the script depends on `afplay`

### 12. Offline mode

Core project functionality does not require cloud connectivity.

Offline-capable once tools are already installed:

- firmware builds
- USB flashing
- UART logging
- Bluetooth Mesh demo operation
- host audio bridge

Potentially online-only ahead of time:

- initial installation of Nordic tooling
- initial installation of Python dependency `pyserial`
- downloading official Nordic documentation

### 13. Security keys and token handling

The project uses locally created Bluetooth Mesh credentials in the `nRF Mesh` app.

Recommendations:

- create your own mesh network and app key locally
- do not commit exported mesh configurations with real keys
- store any exported mesh backup privately

Current firmware credential:

- the controller clear-alert password is hardcoded in `firmware/controller/src/model_handler.c`
- current value: `1234`

For reuse outside the classroom demo:

- change `CONTROLLER_CLEAR_PASSWORD`
- treat `1234` as a demo password only

## Notes and limitations

- no custom hardware was used
- no batteries were used
- no cloud backend is required
- no formal RF, latency, or energy benchmark numbers are included
- this is a reproducible academic prototype, not a production-certified alarm product

## References

- Nordic nRF54L15 DK overview: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-DK
- Nordic nRF54L15 DK hardware files: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-DK/Hardware-files
- Nordic nRF54L15 DK getting started: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-DK/GetStarted
- Nordic nRF54L15 SoC page: https://www.nordicsemi.com/Products/nRF54L15
