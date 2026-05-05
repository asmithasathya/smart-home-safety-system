# Project Updates by Board

This document summarizes how each application board was changed from the original Nordic sample it was copied from. It is intended to give a clear, report-ready explanation of the project work without listing every code change line by line.

## Board 1: Entryway Controller (`firmware/controller/`)

Original sample:
- Nordic Bluetooth Mesh `light_switch`

What the original sample did:
- Acted as a generic mesh light switch.
- Used the board buttons to toggle remote lights on and off.
- Treated each client/button as a mostly independent control path.

What was changed for this project:
- Repurposed the board into the smart home system controller instead of a generic light switch.
- Changed the four buttons from toggle actions into fixed commands:
  - `Button 0` sends `HOME`
  - `Button 1` sends `AWAY`
  - `Button 2` sends `NIGHT`
  - `Button 3` starts the `CLEAR ALERT` flow
- Updated the LED behavior so the controller shows the current active mode instead of acting like four separate switch indicators.
  - `LED 0` indicates `Home`
  - `LED 1` indicates `Away`
  - `LED 2` indicates `Night`
  - `LED 3` gives short feedback when the clear-alert action is requested
- Added clearer UART logging so the controller prints meaningful system actions such as `Sending HOME` instead of only generic button or model information.
- Added a controller-side UART password confirmation step for clearing an alert, so pressing `CLEAR ALERT` alone is not enough to silence the system.
- Kept the underlying Bluetooth Mesh framework from the sample, but changed its role from light toggling to whole-system control.

Why these changes mattered:
- This turned Board 1 into a true front-door control panel for the apartment safety demo.
- It made the demo easier to understand because each button now matches a real apartment mode instead of a generic light function.

## Board 2: Light Node (`firmware/light/`)

Original sample:
- Nordic Bluetooth Mesh `light`

What the original sample did:
- Acted as a basic mesh light node.
- Used Generic OnOff server models mainly to control LEDs as separate light outputs.
- Reflected standard sample light behavior rather than apartment-state behavior.

What was changed for this project:
- Converted the board from a generic light sample into the smart home lighting/status node.
- Reworked the node so the four mesh channels represent shared system states instead of unrelated LED controls:
  - `Home`
  - `Away`
  - `Night`
  - `Alert`
- Added one shared mode state so the board always understands the apartment as being in one main mode at a time.
- Created project-specific LED patterns:
  - `Home` shows a normal safe-state pattern
  - `Away` shows an armed/empty-home pattern
  - `Night` shows a nighttime pattern
  - `Alert` overrides the normal mode and flashes all LEDs
- Added UART status logs such as `MODE: ...` and `ALERT: ...` so the board can be monitored during testing and demo.
- Updated the Bluetooth device/application naming so provisioning shows this node as the smart home light board instead of the generic sample name.

Why these changes mattered:
- This made Board 2 act like a visible room-status display for the apartment.
- It also gave the demo an easy way to show that mesh messages are propagating correctly across boards.

## Board 3: Alarm Node (`firmware/alarm/`)

Original sample:
- Nordic Bluetooth Mesh `light`

What the original sample did:
- Acted as another basic mesh light node.
- Used standard light/on-off server behavior with no intrusion or security logic.

What was changed for this project:
- Converted the board into the apartment alarm node instead of a simple light device.
- Added project-specific safety state tracking:
  - current mode (`Home`, `Away`, `Night`)
  - whether the system is armed
  - whether an alert is active
- Mapped the modes to alarm behavior:
  - `Home` disarms the alarm
  - `Away` arms the alarm
  - `Night` arms the alarm
- Added an intrusion trigger using the board button so the team can demonstrate the alarm without extra hardware sensors.
- Programmed the alarm behavior so:
  - if the board is disarmed, an intrusion is ignored
  - if the board is armed, the board activates the alert and publishes `Alert ON` to the mesh
- Added an OnOff client model so the alarm board can actively publish the alert event, not just receive mode commands.
- Added alert LED flashing and UART messages such as `INTRUSION: DETECTED`, `MODE: ...`, and `ALERT: ACTIVE/CLEAR`.
- Kept the mesh provisioning and settings framework from the original sample, but changed the board’s role completely from lighting to security.

Why these changes mattered:
- This made Board 3 the main event-producing node in the system rather than just another listener.
- It gave the project a clear cause-and-effect demo: mode selection arms or disarms the apartment, and an intrusion then triggers a network-wide alarm.

## Overall Project Impact

Across all three boards, the main project work was not simply copying Nordic examples, but reshaping them into a coordinated apartment safety system. The original samples were mostly standalone mesh lighting demos. In the final project, they were adapted into:

- a dedicated controller board
- a room-status light board
- an armed/disarmed alarm board

Together, the boards now demonstrate multi-node Bluetooth Mesh communication, coordinated mode changes, alert propagation, and project-specific human interaction through buttons, LEDs, and UART logging.
