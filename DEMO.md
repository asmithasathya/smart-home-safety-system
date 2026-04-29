# Smart Home Safety System Demo Script

Use this script for the final in-class demo. It assumes all three boards are already flashed and provisioned into the same Bluetooth Mesh network.

## 1. Prep The Boards

1. Connect the controller, light, and alarm boards to the laptop.
2. Confirm the boards are powered and already provisioned in nRF Mesh.
3. Close `screen`, serial terminals, or any other program using the board UART ports.
4. List the visible ports:

```bash
python3 tools/meshguard_command_center.py --list-ports
```

If the ports are not already known, connect one board at a time and rerun the command so each port can be labeled as `controller`, `light`, or `alarm`.

## 2. Start The Visual Command Center

Run from the repo root:

```bash
python3 tools/meshguard_command_center.py \
  --source controller=/dev/cu.usbmodemCONTROLLER \
  --source light=/dev/cu.usbmodemLIGHT \
  --source alarm=/dev/cu.usbmodemALARM \
  --port 8420 \
  --desktop-audio
```

Open the dashboard on the laptop:

```bash
http://localhost:8420
```

Optional phone display:

Open the `http://...:8420` LAN URL printed by the command center on a phone that is on the same Wi-Fi network.

### Three-Laptop Setup

If each board is plugged into a different laptop, use one laptop as the main command center and run one UART agent on each teammate laptop.

On the main laptop with the light board:

```bash
python3 tools/meshguard_command_center.py \
  --source light=/dev/cu.usbmodemLIGHT \
  --port 8420 \
  --desktop-audio
```

On the controller laptop:

```bash
python3 tools/meshguard_uart_agent.py \
  --source controller \
  --port /dev/cu.usbmodemCONTROLLER \
  --command-center http://MAIN-LAPTOP-IP:8420
```

On the alarm laptop:

```bash
python3 tools/meshguard_uart_agent.py \
  --source alarm \
  --port /dev/cu.usbmodemALARM \
  --command-center http://MAIN-LAPTOP-IP:8420
```

Use the actual `http://...:8420` URL printed by the main command center for `--command-center`.

The agent terminals should stay open for the whole demo. They forward board logs and send heartbeats so the main dashboard knows each board is still connected.

## 3. Enable Sounds

1. On the browser dashboard, click `Enable Audio`.
2. Keep `--desktop-audio` enabled in the command so the laptop speaker also plays the alert loop.
3. Confirm the dashboard shows `Audio Ready`.

## 4. Run The Full Demo

1. Press controller `Button 0` for `HOME`.
2. Confirm the dashboard shows `HOME MODE ENGAGED`.
3. Press alarm `Button 0` while in Home.
4. Confirm the alarm board logs ignored intrusion and the dashboard timeline shows `Intrusion ignored`.
5. Press controller `Button 1` for `AWAY`.
6. Confirm the dashboard shows armed Away mode.
7. Press alarm `Button 0` while Away is armed.
8. Confirm all boards enter alert, the dashboard switches to `ALERT: BEDROOM ALARM`, and sound plays.
9. Press controller `Button 3` for clear alert.
10. Confirm the dashboard returns to the current mode and sound stops.
11. Press controller `Button 2` for `NIGHT`.
12. Confirm the Night sound plays once and the dashboard shows `NIGHT MODE ENGAGED`.
13. Press alarm `Button 0` again.
14. Confirm alert returns and all boards flash.
15. Press controller `Button 3` to clear alert for the final all-clear state.

## 5. Backup Visual Demo

If UART setup fails right before the presentation, run the visual dashboard in demo mode:

```bash
python3 tools/meshguard_command_center.py --demo --port 8420
```

This runs a simulated sequence for the laptop and phone dashboard only. Use the real boards separately if needed.
