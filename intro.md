# Smart Home Safety Mesh

Step into a safer home with a lightweight, wireless safety network built for real-world spaces like dorms, apartments, and small homes. This project delivers a complete **Smart Home Safety System** using three Nordic `nRF54L15 DK` boards connected through Bluetooth Mesh: an entryway controller, a living-room light node, and a bedroom alarm node. With one button press, users can switch between `Home`, `Away`, and `Night` modes and see synchronized feedback across devices. When an intrusion is simulated while armed, the system instantly raises a network-wide alert and optionally plays alarm audio through a laptop bridge.  

What makes this useful is its balance of simplicity and reliability: no custom wiring, no cloud dependency, and clear local control. Our implementation successfully demonstrates end-to-end mesh communication, synchronized state transitions, intrusion-triggered global alerts, and password-confirmed alert clearing, making it a practical prototype for low-cost, privacy-friendly smart-home safety.

## System Figure

