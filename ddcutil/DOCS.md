# DDC/CI Monitor Control - Documentation

Control your monitor's brightness, contrast, input source and power directly
from Home Assistant using DDC/CI — no physical buttons needed.

## How it works

DDC/CI (Display Data Channel / Command Interface) is a protocol built into
most modern monitors. It communicates over a separate I2C channel inside your
video cable, completely independent of which input is currently active on
screen. This means your Raspberry Pi (connected on HDMI2, for example) can
control the monitor even while you are using PC1 on HDMI1.

## Prerequisites

- A monitor with DDC/CI support (most monitors manufactured after 2005)
- DDC/CI enabled in your monitor's OSD menu (usually under "Setup" or "Advanced")
- I2C enabled on your Home Assistant OS host (see below)
- For MQTT: the Mosquitto add-on installed and running

## Enabling I2C on Home Assistant OS (Raspberry Pi)

If you are running Home Assistant OS on a Raspberry Pi, you need to enable
I2C before the add-on can communicate with your monitor. Open the Terminal
& SSH add-on and run:

```bash
mkdir -p /mnt/boot/CONFIG/modules
echo i2c-dev > /mnt/boot/CONFIG/modules/rpi-i2c.conf
echo dtparam=i2c_vc=on >> /mnt/boot/config.txt
echo dtparam=i2c_arm=on >> /mnt/boot/config.txt
sync && reboot
```

After rebooting, verify I2C is active:

```bash
ls /dev/i2c-*
```

You should see one or more `/dev/i2c-N` devices.

## Installation

1. Add this repository to Home Assistant:
   **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
   Paste: `https://github.com/YOUR_USERNAME/addon-ddcutil`

2. Find **DDC/CI Monitor Control** in the store and click **Install**.

3. Start the add-on and check the **Log** tab.

## Finding your input source VCP values

On first startup, the add-on automatically detects your monitor's capabilities
and presents them in two ways:

**In the Log tab:** Look for the section that reads:

```
============================================================
Monitor detected: Dell U2722D
------------------------------------------------------------
Available input sources (use these in your config):
  VCP Value: 17    → HDMI-1
  VCP Value: 18    → HDMI-2
  VCP Value: 15    → DisplayPort-1
============================================================
```

**In a file:** A `capabilities.txt` file is written to your add-on config
folder, accessible via Samba or SSH at:
`/addon_configs/<repo_hash>_ddcutil/capabilities.txt`

## Configuration

### Basic (no MQTT)

```yaml
log_level: info
mqtt_enabled: false
input_sources:
  - vcp_value: 17
    alias: "Gaming PC"
  - vcp_value: 18
    alias: "Home Assistant"
  - vcp_value: 15
    alias: "Laptop"
```

### With MQTT (recommended)

```yaml
log_level: info
mqtt_enabled: true
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_username: your_mqtt_user
mqtt_password: your_mqtt_password
mqtt_topic_prefix: ddcutil
mqtt_discovery: true
mqtt_discovery_prefix: homeassistant
poll_enabled: false
poll_interval: 600
input_sources:
  - vcp_value: 17
    alias: "Gaming PC"
  - vcp_value: 18
    alias: "Home Assistant"
  - vcp_value: 15
    alias: "Laptop"
```

### Configuration options

| Option | Default | Description |
|---|---|---|
| `log_level` | `info` | Logging verbosity |
| `mqtt_enabled` | `false` | Enable MQTT integration |
| `mqtt_host` | `core-mosquitto` | MQTT broker hostname or IP |
| `mqtt_port` | `1883` | MQTT broker port |
| `mqtt_username` | `` | MQTT username (leave empty if not needed) |
| `mqtt_password` | `` | MQTT password (leave empty if not needed) |
| `mqtt_topic_prefix` | `ddcutil` | Prefix for all MQTT topics |
| `mqtt_discovery` | `true` | Auto-create HA entities via MQTT discovery |
| `mqtt_discovery_prefix` | `homeassistant` | HA MQTT discovery prefix |
| `poll_enabled` | `false` | Poll monitor state periodically |
| `poll_interval` | `600` | Poll interval in seconds (min 60) |
| `input_sources` | `[]` | Input source alias mappings |

## Home Assistant entities

When MQTT discovery is enabled, the following entities are created
automatically under a single **device** named after your monitor:

| Entity | Type | Description |
|---|---|---|
| Brightness | `light` | Controls brightness (0–100%) and power |
| Contrast | `number` | Controls contrast (0–100%) |
| Input Source | `select` | Switches between your configured input aliases |
| Power | `switch` | Turns monitor on or off |

## Using in automations

### Dim monitor at sunset

```yaml
automation:
  trigger:
    platform: sun
    event: sunset
  action:
    service: light.turn_on
    target:
      entity_id: light.brightness
    data:
      brightness_pct: 30
```

### Switch input at a scheduled time

```yaml
automation:
  trigger:
    platform: time
    at: "09:00:00"
  action:
    service: select.select_option
    target:
      entity_id: select.input_source
    data:
      option: "Gaming PC"
```

## Shell command mode (no MQTT)

If MQTT is disabled you can still control the monitor using shell commands
directly in automations:

```yaml
# configuration.yaml
shell_command:
  monitor_brightness: "docker exec addon_ddcutil ddcutil setvcp 0x10 {{ brightness }}"
  monitor_input: "docker exec addon_ddcutil ddcutil setvcp 0x60 {{ vcp_value }}"
```

## A note on polling

Polling is disabled by default. The DDC/CI protocol communicates over I2C and
is inherently slow (~100–500ms per command). Aggressive polling can stress the
I2C bus and cause some monitors to become unresponsive. The add-on uses an
event-driven approach — it reads monitor state once on startup and then only
after a command is executed.

If you enable polling, use a minimum interval of 60 seconds and prefer 600
seconds (10 minutes) or more.

## Troubleshooting

**No monitor detected**
- Confirm DDC/CI is enabled in your monitor OSD
- Check `/dev/i2c-*` devices exist: `ls /dev/i2c-*`
- Run `ddcutil detect --verbose` in the terminal for detailed diagnostics

**I2C devices not found**
- Follow the I2C enable steps above for your platform
- Check kernel module: `lsmod | grep i2c`

**MQTT entities not appearing in HA**
- Confirm the Mosquitto add-on is running
- Check MQTT credentials in the add-on config
- Ensure `mqtt_discovery` is `true` and the discovery prefix matches HA settings

**Input source not switching**
- Verify the VCP value in your config matches the value in `capabilities.txt`
- Some monitors only accept input switch commands when the target input has an
  active signal

## Support

- [GitHub Issues](https://github.com/YOUR_USERNAME/addon-ddcutil/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io)
