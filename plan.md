# Smart Home Safety System Plan

## Summary

Build the project inside `smart-home-safety-system/`, which is the actual shared Git repo in this workspace. Use three separate Zephyr Bluetooth Mesh apps so each teammate can flash one nRF54L15 DK independently: `controller`, `light-node`, and `alarm-node`.

For the first lab-ready version, do not use Bluetooth Mesh Scene storage even though it appears in the slides. Use four fixed Generic OnOff mesh channels instead: `Home`, `Away`, `Night`, and `Alert`. This keeps the behavior from the proposal, but removes fragile scene setup and makes provisioning/debugging much easier.

## Implementation Steps

1. Scaffold `smart-home-safety-system/` with three app folders, one small shared `common` module, and short docs for build, provisioning, and demo steps. Keep the Nordic mesh sample sysbuild layout in each app so `ipc_radio` is built automatically for `nrf54l15dk/nrf54l15/cpuapp`.

2. Add a shared state interface in `common` with `enum safety_mode { HOME, AWAY, NIGHT }`, `struct node_state { mode, armed, alert_active }`, shared log strings, and LED-pattern helpers. Default every node to `HOME`, `armed=false`, `alert_active=false` on boot. Keep mesh/settings persistence enabled for provisioning data, but do not persist armed/mode state in v1.

3. Build the `controller` app from the Nordic `light_switch` sample. Keep four Generic OnOff Clients, but change them from toggle behavior to fixed actions: `Button 0 -> Home ON`, `Button 1 -> Away ON`, `Button 2 -> Night ON`, `Button 3 -> Alert OFF` to clear alarms. Add one Generic OnOff Server subscribed to `Alert` so the controller also receives global alarm state. Idle LEDs should show current mode as `LED0=Home`, `LED1=Away`, `LED2=Night`; active alert should override this and flash all LEDs. UART logs should print `MODE: ...` and `ALERT: ...`.

4. Build the `light-node` app from the Nordic `light` sample. Replace the default “one LED per server” meaning with four logical Generic OnOff Servers: `Home`, `Away`, `Night`, and `Alert`. The three mode servers update `current_mode`; the alert server updates `alert_active`. Idle display should be `Home -> LED0 solid`, `Away -> LED1 solid`, `Night -> LED2+LED3 solid`; alert display should flash all LEDs until `Alert OFF` is received.

5. Build the `alarm-node` app from the Nordic `light` sample and add one Generic OnOff Client for publishing alarms. Keep four Generic OnOff Servers as `Home`, `Away`, `Night`, and `Alert`. Map modes to arming as `HOME = disarmed`, `AWAY = armed`, `NIGHT = armed`. `Button 0` simulates intrusion. If disarmed, only log `INTRUSION: IGNORED`; if armed, set local alert active and publish `Alert ON` to the `Alert` group. When its alert server receives `Alert OFF`, clear the local alarm and return to the current mode display.

6. Standardize the build/flash workflow from an NCS shell where `west` is available. Use the same board target for all three apps:

```bash
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/controller smart-home-safety-system/controller
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/light smart-home-safety-system/light-node
west build -p -b nrf54l15dk/nrf54l15/cpuapp -d build/alarm smart-home-safety-system/alarm-node
```

Flash each board from its corresponding build directory.

1. Write a provisioning guide for the nRF Mesh mobile app. Create one mesh network, one application key, and four groups named `Home`, `Away`, `Night`, and `Alert`. Provision all three boards, bind all OnOff models to the same app key, set the controller clients’ publish addresses to the four groups, subscribe the light/alarm mode servers to `Home/Away/Night`, subscribe all alert servers to `Alert`, and set the alarm node’s alert client publication to `Alert`.

2. Add a short demo script in the repo so every teammate can reproduce the lab in the same order: provision, flash, press `Home`, test ignored intrusion, press `Away`, trigger alarm, clear alarm, press `Night`, trigger alarm again, clear alarm.

## Mesh Interface

| Logical channel | Publisher | Subscribers | Meaning |
| --- | --- | --- | --- |
| `Home` | Controller Button 0 client | Light Home server, Alarm Home server | Set all nodes to Home and disarm alarm node |
| `Away` | Controller Button 1 client | Light Away server, Alarm Away server | Set all nodes to Away and arm alarm node |
| `Night` | Controller Button 2 client | Light Night server, Alarm Night server | Set all nodes to Night and arm alarm node |
| `Alert` | Alarm client publishes `ON`; Controller Button 3 client publishes `OFF` | Controller alert server, Light alert server, Alarm alert server | Global alarm active/cleared |

## Test Plan

1. Confirm all three apps build successfully for `nrf54l15dk/nrf54l15/cpuapp` and each sysbuild also produces `ipc_radio`.
2. Provision all three boards into one mesh network and verify UART shows successful mesh initialization on each board.
3. Press controller `Home` and confirm controller, light node, and alarm node all show Home; alarm node must be disarmed.
4. Press the alarm trigger while in Home and confirm only the alarm node logs an ignored intrusion; no board should enter alert mode.
5. Press controller `Away` and confirm both remote nodes change mode and the alarm node becomes armed.
6. Press the alarm trigger while in Away and confirm all three boards flash alert LEDs and all UART terminals report `ALERT: ACTIVE`.
7. Press controller `Clear` and confirm all three boards stop flashing and return to the current mode display.
8. Repeat the alarm test in `Night` and confirm Night uses a different idle LED pattern from Away.
9. Power-cycle the boards after provisioning and confirm mesh credentials persist, but v1 state resets to `HOME`, `armed=false`, `alert_active=false`.

## Assumptions

- The project repo to implement is `smart-home-safety-system/`, not the whole `embedded-sys` workspace.
- Board buttons are the only inputs in v1; no external PIR, reed switch, or extra sensor hardware is required.
- The first deliverable is the core demo only; stretch goals like NVS armed-state restore, low-power tuning, and node-drop detection are deferred until the base system is stable.
