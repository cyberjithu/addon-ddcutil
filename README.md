# addon-ddcutil

[![License][license-shield]](LICENSE)
![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armv7 Architecture][armv7-shield]

Control your monitor's brightness, contrast, input source and power directly
from Home Assistant using DDC/CI — no physical buttons needed.

DDC/CI communicates over a separate I2C channel built into your video cable,
completely independent of which input is active on screen. This means your
Raspberry Pi (connected on HDMI, for example) can control the monitor even
while you are using another PC on a different input.

---

## Features

- Brightness, contrast, input switching and power on/off via DDC/CI
- MQTT integration with Home Assistant auto-discovery
- User-defined input source aliases (e.g. "Gaming PC", "Laptop")
- Ingress web UI in the HA sidebar — monitor info, state gauges, input map
- **Dynamic I2C bus detection** — automatically finds monitor on any bus
- Automatic capabilities dump to log and file on startup
- Event-driven architecture — no aggressive I2C polling by default
- Brightness lock detection — warns when Eye Saver/HDR blocks brightness
- Multi-architecture: amd64, aarch64, armv7

---

## Prerequisites

Before installing the add-on, make sure the following are in place.

### 1. A DDC/CI capable monitor

Most monitors manufactured after 2005 support DDC/CI. You need to enable it
in your monitor's OSD menu — look under **Setup**, **Advanced**, or
**Display** settings for an option called **DDC/CI** and turn it on.

### 2. A suitable video cable

The cable between your Home Assistant device and the monitor must carry the
DDC/CI signal. HDMI and DisplayPort cables support this by default. VGA does
not.

### 3. I2C enabled on your system

#### Raspberry Pi (Home Assistant OS)

Home Assistant OS is a managed environment — you cannot enable I2C the usual
way. Instead, open the **Terminal & SSH** add-on (or connect a keyboard and
screen directly to the device).

> ⚠️ **Important:** The Terminal & SSH add-on opens the **HA CLI** by default,
> not a full Linux shell. If you see a `ha>` prompt or get errors like
> `unknown command` when running `mkdir`, you are in the HA CLI.
> Type `login` first to drop into a real root shell before continuing.

```bash
login
```

Once you see a standard bash prompt (`#`), run:

```bash
mkdir -p /mnt/boot/CONFIG/modules
echo "i2c-dev" > /mnt/boot/CONFIG/modules/rpi-i2c.conf
sync && reboot
```

After rebooting, verify that I2C devices are present:

```bash
ls /dev/i2c-*
# Expected output: /dev/i2c-0  /dev/i2c-1  (one or more devices)
```

#### Raspberry Pi 4B — Additional DDC/CI fix

The RPi 4B requires two extra config.txt parameters to expose the HDMI DDC/CI
channel to userspace. Without these, `ddcutil detect` returns "No displays
found" even when the monitor is connected and DDC/CI is enabled.

After `login` on the real host shell:

```bash
# Switch to KMS driver (required for DDC/CI on RPi4)
sed -i 's/dtoverlay=vc4-fkms-v3d/dtoverlay=vc4-kms-v3d/' /mnt/boot/config.txt

# Unlock HDMI I2C bus for userspace access
echo "dtparam=i2c2_iknowwhatimdoing" >> /mnt/boot/config.txt

# Verify changes
grep -i "vc4\|i2c2" /mnt/boot/config.txt

sync && reboot
```

> ℹ️ The `i2c2_iknowwhatimdoing` parameter name is intentional — it's the
> official RPi parameter that releases the HDMI I2C bus from exclusive GPU
> control and grants userspace access.

After reboot, the add-on should detect your monitor automatically.

**Which HDMI port to use on RPi 4B:**
The port **closest to the USB-C power connector** (HDMI0) works most
reliably for DDC/CI. Connect your monitor cable there.

#### x86-64 (generic PC running Home Assistant OS)

I2C is usually available by default. Verify with:

```bash
ls /dev/i2c-*
```

### 4. Monitor OSD settings

Certain monitor features **lock brightness control** and prevent DDC/CI
brightness commands from taking effect. Before using the add-on, disable
the following in your monitor's OSD:

- **Eye Saver Mode** / Eye Care
- **HDR** / HDR Mode
- **Dynamic Contrast** / Smart Contrast
- **Eco Saving** / Eco Mode
- **Auto Brightness**

> ⚠️ **Samsung monitors:** These features completely hide the brightness VCP
> feature from DDC/CI when enabled. The add-on will warn in the log if
> brightness control is locked.

### 5. MQTT broker (optional but recommended)

For full Home Assistant integration, install the
[Mosquitto add-on](https://github.com/home-assistant/addons/tree/master/mosquitto)
from the official add-on store. The add-on works without MQTT but you will
only have access to the web UI and shell commands.

---

## Installation

### Step 1 — Add this repository to Home Assistant

1. Go to **Settings → Add-ons → Add-on Store**
2. Click **⋮** (top right) → **Repositories**
3. Paste the following URL and click **Add**:
   ```
   https://github.com/cyberjithu/addon-ddcutil
   ```
4. Scroll down to find **DDC/CI Monitor Control** and click **Install**

### Step 2 — Configure before starting

Go to the **Configuration** tab. At minimum set:

```yaml
log_level: info
mqtt_enabled: false
input_sources: []
```

Leave `input_sources` empty for now — the add-on will discover them for you
on first start.

### Step 3 — Start and find your input source VCP values

Start the add-on and open the **Log** tab. On startup the add-on detects your
monitor and prints all available input sources:

```
============================================================
Monitor detected: Samsung Neo G9
------------------------------------------------------------
Available input sources (use these in your config):
  VCP Value: 1     → VGA-1
  VCP Value: 17    → HDMI-1
  VCP Value: 18    → HDMI-2
  VCP Value: 15    → DisplayPort-1
============================================================
```

The same information is also written to a file you can access via Samba or
SSH:

```
/addon_configs/<repo_hash>_ddcutil/capabilities.txt
```

> ℹ️ Note: Some monitors (including Samsung Neo G9) report `Maximum retries
> exceeded` for capabilities. This is a known firmware quirk — individual VCP
> commands still work correctly. Use `ddcutil getvcp 60` to find your input
> source values manually if needed.

### Step 4 — Map your input sources

Go back to **Configuration** and add your aliases using the VCP values from
the log:

```yaml
input_sources:
  - vcp_value: 17
    alias: "Gaming PC"
  - vcp_value: 18
    alias: "Home Assistant"
  - vcp_value: 15
    alias: "Laptop"
```

Save and restart the add-on.

### Step 5 — Enable MQTT (optional)

To get controllable entities in Home Assistant, configure MQTT:

```yaml
mqtt_enabled: true
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_username: your_mqtt_username
mqtt_password: your_mqtt_password
mqtt_discovery: true
```

Save and restart. Home Assistant will automatically create the following
entities under a device named after your monitor:

| Entity | Type | What it controls |
|---|---|---|
| Brightness | `light` | Brightness (0–100%) and power |
| Contrast | `number` | Contrast (0–100%) |
| Input Source | `select` | Active input using your aliases |
| Power | `switch` | Monitor on/off |

---

## Using the web UI

After starting the add-on, a **Monitor Control** panel appears in your Home
Assistant sidebar. Click it to open the ingress dashboard.

The dashboard shows:

- **Monitor info** — name, manufacturer, model and I2C bus
- **Current state** — brightness and contrast gauges, active input, power status
- **Input source map** — all configured aliases with the currently active one highlighted
- **Full capabilities** — raw DDC/CI capabilities string (expandable)

A `/api/state` JSON endpoint is also available for debugging.

---

## Using in Home Assistant automations

### Dim the monitor at sunset

```yaml
automation:
  alias: "Dim monitor at sunset"
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

### Switch input source on a schedule

```yaml
automation:
  alias: "Switch to Gaming PC at 9am"
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

### Turn off monitor when leaving home

```yaml
automation:
  alias: "Monitor off when away"
  trigger:
    platform: state
    entity_id: person.your_name
    to: "not_home"
  action:
    service: switch.turn_off
    target:
      entity_id: switch.power
```

---

## Troubleshooting

**`unknown command` or `mkdir: not found` when running I2C setup commands**

You are in the **HA CLI**, not a real Linux shell. The Terminal & SSH add-on
drops you into the HA supervisor CLI by default, which only understands `ha`
commands. Type `login` first to get a proper root shell:

```bash
login
```

You should now see a `#` prompt. Run your commands from there.

**No monitor detected on Raspberry Pi 4B**

This is the most common issue on RPi4. The vc4 GPU driver holds exclusive
control of the HDMI I2C bus by default. Apply the fix:

```bash
# After login on real host
sed -i 's/dtoverlay=vc4-fkms-v3d/dtoverlay=vc4-kms-v3d/' /mnt/boot/config.txt
echo "dtparam=i2c2_iknowwhatimdoing" >> /mnt/boot/config.txt
sync && reboot
```

Also make sure to use **HDMI0** (the port closest to the USB-C power connector)
— this port has the most reliable DDC/CI support on RPi4.

**No I2C devices found (`/dev/i2c-*` missing)**

Re-run the I2C enable steps. Check kernel module is loaded:

```bash
lsmod | grep i2c
# Expected: i2c_dev  20480  2
```

**Brightness not changing**

Check your monitor OSD and disable: Eye Saver, HDR, Dynamic Contrast, Eco
Saving. These lock the brightness VCP feature. The add-on will log a warning
if brightness is locked.

**`DDCRC_VERIFY` errors in log**

This is a known Samsung firmware quirk — the monitor accepts and applies the
command but returns an invalid response during verification. The add-on uses
`--noverify` to handle this automatically. Commands still work correctly.

**Web UI not appearing in sidebar**

Confirm `ingress: true` is present in `config.yaml`. Reload the HA browser
tab after starting the add-on.

**MQTT entities not appearing in Home Assistant**

Check the Mosquitto add-on is running. Verify your MQTT credentials. Make
sure `mqtt_discovery` is `true` and the discovery prefix matches your HA
MQTT integration settings (default is `homeassistant`).

**Input source not switching**

Verify the VCP value in your config matches the value shown in
`capabilities.txt`. Some monitors only accept input switch commands when the
target input has an active signal connected to it. Use `--noverify` flag
(handled automatically by the add-on).

**Samsung Neo G9 specific notes**

- Connect via **HDMI** not DisplayPort — DDC/CI only works over HDMI on this monitor
- Use **HDMI0** on RPi4 (closest to USB-C power)
- Disable Eye Saver, HDR, Dynamic Contrast in OSD for brightness control
- Capabilities command returns "Maximum retries exceeded" — this is normal,
  individual VCP commands work correctly
- `DDCRC_VERIFY` errors are expected and handled automatically

---

## Roadmap

| Version | Planned features |
|---|---|
| v1.1 | ✅ Ingress web UI, dynamic bus detection, --noverify support, brightness lock detection |
| v1.2 | Interactive web UI — set brightness and switch input from the dashboard |
| v2.0 | Multi-monitor support |

---

## Support

- [Open an issue on GitHub](https://github.com/cyberjithu/addon-ddcutil/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io)
- [Home Assistant Discord](https://discord.gg/home-assistant)

---

## License

MIT License — see [LICENSE](LICENSE)

[license-shield]: https://img.shields.io/github/license/cyberjithu/addon-ddcutil.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
