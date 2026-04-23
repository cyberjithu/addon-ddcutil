# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-04-23

### Added

- Ingress web UI accessible from Home Assistant sidebar
- Read-only dashboard showing monitor info, current state and input source map
- Visual gauges for brightness and contrast with progress bars
- Active input source indicator
- Collapsible raw capabilities view
- `/api/state` JSON endpoint for debugging
- Atomic state file writes (`state.json`) — race-condition safe via `os.replace()`
- Dynamic I2C bus detection — automatically scans all buses, no hardcoded list
- `full_access: true` — works on any hardware without device list configuration
- `--noverify` flag on all setvcp commands — fixes DDCRC_VERIFY errors on Samsung monitors
- Brightness lock detection — warns when Eye Saver/HDR/Dynamic Contrast blocks brightness
- `device_tree: true` for proper hardware device access

### Fixed

- Raspberry Pi 4B DDC/CI detection via `vc4-kms-v3d` driver and `i2c2_iknowwhatimdoing`
- EPERM errors on i2c devices resolved by `full_access: true`
- Samsung Neo G9 DDCRC_VERIFY errors handled automatically with `--noverify`
- Dynamic bus detection handles any bus number (no more hardcoded i2c-10/i2c-22)

### Changed

- Removed hardcoded `devices:` list — `full_access: true` covers all hardware
- Removed `extra_i2c_buses` config option — no longer needed
- Switched from `vc4-fkms-v3d` to `vc4-kms-v3d` recommendation for RPi4

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
