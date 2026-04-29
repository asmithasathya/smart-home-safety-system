# Smart Home Safety System

This repo contains the code for a 3-board smart home safety system built for the nRF54L15 DK. The system is intended to use Bluetooth Mesh so that each board can be flashed separately and still work together as one apartment safety demo.

Current status:
- `controller/` is implemented for Board 1 (`Entryway Controller`)
- Board 2 and Board 3 can be added to this same repo later

## Repo Setup

Use an `nRF Connect SDK` terminal so `west` and the correct toolchain are available.

Recommended environment:
- nRF Connect SDK `v3.2.1`
- Zephyr toolchain installed through Nordic
- `nRF Mesh` mobile app installed on a phone
- 1 or more `nRF54L15 DK` boards

Board target used in this repo:

```bash
nrf54l15dk/nrf54l15/cpuapp
```

From the repo root:

```bash
cd /Users/asmitha/embedded-sys/smart-home-safety-system
```

## Board 1: Entryway Controller

The Board 1 app lives in:

```bash
controller/
```

### Build Board 1

```bash
cd /Users/asmitha/embedded-sys/smart-home-safety-system
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/controller controller
```

### Flash Board 1

```bash
cd /Users/asmitha/embedded-sys/smart-home-safety-system
west flash --build-dir build/controller
```

### Open the UART Log

```bash
ls /dev/cu.usbmodem*
screen /dev/cu.usbmodemXXXX 115200
```

Expected boot messages include:
- `Bluetooth initialized`
- `Mesh initialized`

### Board 1 Button Mapping

- `Button 0` -> `HOME`
- `Button 1` -> `AWAY`
- `Button 2` -> `NIGHT`
- `Button 3` -> `CLEAR ALERT`

### Board 1 LED Behavior

- `LED 0` shows `Home`
- `LED 1` shows `Away`
- `LED 2` shows `Night`
- `LED 3` gives brief feedback when `CLEAR ALERT` is sent

### Summary of Changes from the Original Nordic Sample

Board 1 was based on Nordic’s Bluetooth Mesh `light_switch` sample, but it was changed from a generic light-toggle client into the `Entryway Controller` for this project. The original sample toggled remote lights using button presses; our version changed that behavior so the four buttons send fixed control actions: `HOME`, `AWAY`, `NIGHT`, and `CLEAR ALERT`.

We also changed the local board behavior so it acts like a system mode selector instead of four independent switches. Only one mode LED is shown at a time, UART logs print readable action names like `Sending HOME`, and Button 3 briefly flashes `LED 3` to confirm the clear-alert action without changing the current mode display.

## Bluetooth Mesh Setup for Board 1

These steps configure the phone app and add Board 1 to the mesh network.

### 1. Create a Mesh Network

1. Open the `nRF Mesh` app on your phone.
2. Create a new network.
3. Name it something like `SmartHomeSafety`.

### 2. Provision Board 1

1. Power on the flashed Board 1.
2. In the `nRF Mesh` app, scan for unprovisioned devices.
3. Select the device advertising as `Mesh Light Switch`, or match it using the UUID shown in the UART log.
4. When asked for OOB type, select `No OOB`.
5. Finish provisioning.
6. Rename the node to `Entryway Controller`.

### 3. Create the Mesh Groups

Inside the `nRF Mesh` app, create these 4 groups:

- `Home`
- `Away`
- `Night`
- `Alert`

If the app suggests group addresses automatically, keep the defaults.

### 4. Create an Application Key

1. Open the mesh network settings.
2. Go to `App Keys` or `Application Keys`.
3. Add one application key.
4. Name it `App Key 1`.
5. If asked for subnet/network key, use the default or primary one.

### 5. Add the Application Key to Board 1

1. Open the `Entryway Controller` node in the app.
2. Open the node configuration.
3. Add `App Key 1` to the node.

This must be done before binding models.

### 6. Bind and Configure the Four Client Models

Configure each `Generic OnOff Client` model like this:

- `Element 1` -> bind to `App Key 1`, publish to `Home`
- `Element 2` -> bind to `App Key 1`, publish to `Away`
- `Element 3` -> bind to `App Key 1`, publish to `Night`
- `Element 4` -> bind to `App Key 1`, publish to `Alert`

### 7. Quick Functional Check

After configuration:

1. Press `Button 0` and check the UART log for `Sending HOME`
2. Press `Button 1` and check for `Sending AWAY`
3. Press `Button 2` and check for `Sending NIGHT`
4. Press `Button 3` and check for `Sending CLEAR ALERT`

The controller should also update its LEDs so that only one mode LED is active at a time, while Button 3 briefly flashes `LED 3`.

## Notes

- Provisioning is stored on the board, so unplugging and replugging the board does not remove it from the mesh network.
- Changing Wi-Fi networks does not matter because Bluetooth Mesh here is independent of Wi-Fi.
- If the board is erased or the mesh network is deleted from the app, provisioning must be repeated.

## Laptop Alarm Bridge Setup (macOS)

Use this to play:
- `alarm.m4a` repeatedly whenever UART logs show `ALERT: ACTIVE`
- `goodnight_sound.mp3` once whenever UART logs show `MODE: NIGHT` or `Sending NIGHT`

For the best demo flow, point this bridge at the `alarm` or `light` board UART so you can keep the `controller` UART free for password entry.

### 1. Create and activate a Python virtual environment

From repo root:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependency

```bash
pip install pyserial
```

### 3. Find your board serial port

```bash
ls /dev/cu.usbmodem*
```

Pick the port for the board whose UART prints the alert logs.

### 4. Test alarm sound playback once

```bash
python3 tools/laptop_alarm_bridge.py --test-sound
```

### 5. Test Night mode sound playback once

```bash
python3 tools/laptop_alarm_bridge.py --test-night-sound
```

### 6. Run the live UART-to-speaker bridge

```bash
python3 tools/laptop_alarm_bridge.py --port /dev/cu.usbmodemXXXXXXXXXXXX --baud 115200
```

This now defaults to:
- `alarm.m4a` for alert playback
- `goodnight_sound.mp3` for Night mode playback

### 7. Optional: use different sound files

```bash
python3 tools/laptop_alarm_bridge.py \
  --port /dev/cu.usbmodemXXXXXXXXXXXX \
  --sound /System/Library/Sounds/Glass.aiff \
  --night-sound goodnight_sound.mp3
```

### 8. Stop the script

Press `Ctrl+C` in the terminal.

### Troubleshooting

- If `--test-sound` works but live mode is silent, verify the correct serial port is used.
- Ensure no other app (`screen`, VS Code serial monitor) is connected to the same port.
- Confirm UART lines include `ALERT: ACTIVE`, `ALERT: CLEAR`, or `MODE: NIGHT`.
