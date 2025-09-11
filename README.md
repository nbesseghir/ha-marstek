# Marstek Energy Storage Integration for Home Assistant

A lightweight integration for Marstek energy storage systems, enabling local control and monitoring via Home Assistant. This integration communicates with the device using UDP and provides sensors, switches, and controls for managing the system.

---

## Features

- **Sensors**: Monitor battery SoC, power (battery, PV, grid), energy counters, temperature, and capacity.
- **Control Modes**: Switch between `Auto`, `AI`, `Manual`, and `Passive` modes.
- **Binary Sensors**: Check charge/discharge permissions.
- **Service**: `marstek.refresh_now` to force an update.

---

## Installation

### HACS (Recommended)
1. Open Home Assistant and go to **HACS → Integrations**.
2. Click the **+ Explore & Download Repositories** button.
3. [![Open your Home Assistant instance and show the add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nbesseghir&repository=ha-marstek)
4. Search for **Marstek** and click **Download**.
5. Restart Home Assistant.

### Manual Installation
1. Download this repository as a ZIP file and extract it.
2. Copy the `custom_components/marstek` folder to your Home Assistant `config` directory.
3. Restart Home Assistant.

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration → "Marstek"**.
2. Enter the following details:
   - **IP Address**: Marstek battery IP.
   - **Device ID**: Default is `0`.
   - **Port**: Default is `30000`.
   - **Scan Interval (s)**: Default is `10`.
   - **Local IP + Port**: Required for strict NAT setups.
   - **Timeout (s)**: Default is `5`.

---

## Troubleshooting

- **No Data?** Verify IP, port, and device ID. Ensure the device is reachable.
- **Strict NAT/Firewall?** Configure `local_IP` and `local_port`.
- **Debug Logs:** Add the following to your `configuration.yaml`:

    ```yaml
    logger:
      default: warning
      logs:
        custom_components.marstek: debug
    ```

---

## License

This integration is licensed under the MIT License.

---

**Good luck & have fun!** 🚀
