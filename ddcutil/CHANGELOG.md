# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-04-21

### Added

- Initial release of DDC/CI Monitor Control
- Monitor auto-detection on startup
- Control brightness, contrast, input source and power via DDC/CI
- MQTT integration with Home Assistant auto-discovery
- `light` entity for brightness and power control
- `number` entity for contrast control
- `select` entity for input source switching
- `switch` entity for power control
- User-defined input source aliases (VCP value → friendly name mapping)
- Capabilities dump to add-on log on startup (Option 1)
- Capabilities written to `capabilities.txt` in addon_configs on startup (Option 2)
- Configurable log level
- Optional slow-poll mode (disabled by default to protect I2C bus)
- Last Will and Testament (LWT) for MQTT availability tracking
- Multi-architecture support: amd64, aarch64, armv7
