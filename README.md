# addon-ddcutil

[![License][license-shield]](LICENSE)
![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armv7 Architecture][armv7-shield]

Home Assistant add-on repository containing **DDC/CI Monitor Control** — control
your monitor's brightness, contrast, input source and power directly from
Home Assistant.

## Add-ons in this repository

### [DDC/CI Monitor Control](ddcutil/)

Control your monitor via DDC/CI using `ddcutil`. Integrates with Home Assistant
via MQTT auto-discovery, creating `light`, `number`, `select` and `switch`
entities automatically.

**Features:**
- Brightness, contrast, input switching, power on/off
- MQTT integration with HA auto-discovery
- User-defined input source aliases
- Automatic capabilities dump on startup
- Event-driven (no aggressive I2C polling by default)
- Multi-architecture: amd64, aarch64, armv7

## Installation

Add this repository to Home Assistant:

1. Go to **Settings → Add-ons → Add-on Store**
2. Click **⋮ → Repositories**
3. Paste: `https://github.com/YOUR_USERNAME/addon-ddcutil`
4. Find **DDC/CI Monitor Control** and install

## License

MIT License — see [LICENSE](LICENSE)

[license-shield]: https://img.shields.io/github/license/YOUR_USERNAME/addon-ddcutil.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
