# Alarm Node Implementation Log

This file is a running record of changes made to the `alarm/` app.

## 2026-04-29

### Goal
Implement alarm-node behavior so that:
- Controller mode messages arm/disarm the alarm node.
- Alarm node button press triggers global alert only when armed.
- Alert propagates to all boards through the `Alert` mesh channel.

### Changes made
- Reworked `alarm/src/model_handler.c` from a plain LED light server into project-specific alarm logic.
- Added four logical Generic OnOff Servers mapped by element/channel:
  - Element 1 server: `Home`
  - Element 2 server: `Away`
  - Element 3 server: `Night`
  - Element 4 server: `Alert`
- Added one Generic OnOff Client on element 1 for publishing `Alert ON` events.
- Added local state model:
  - `mode`: `HOME`, `AWAY`, `NIGHT`
  - `armed`: `false` in Home, `true` in Away/Night
  - `alert_active`: global/local alert state
- Added button behavior:
  - `Button 0` = intrusion simulation
  - If disarmed: log `INTRUSION: IGNORED (DISARMED)` and do nothing else.
  - If armed: set local alert active and publish `Alert ON` to mesh.
- Added LED behavior:
  - Idle: Home -> LED0, Away -> LED1, Night -> LED2+LED3.
  - Alert active: flash all LEDs.
- Added UART logs:
  - `MODE: ... (armed/disarmed)`
  - `ALERT: ACTIVE/CLEAR`
  - intrusion logs when button is pressed.
- Kept mesh provisioning/settings persistence unchanged (still handled by `CONFIG_SETTINGS` + `settings_load()` in main).
- Kept health attention behavior and integrated normal state display restoration after attention mode ends.

### Build config updates
- Updated `alarm/prj.conf` to enable OnOff client support:
  - `CONFIG_BT_MESH_ONOFF_CLI=y`

### Provisioning expectation for this behavior
- Bind and configure the alarm node’s alert client model publication to the `Alert` group.
- Subscribe alarm node alert server (and controller/light alert servers) to `Alert`.
