"""
DDC/CI Monitor Control - Core Logic
Controls monitor via ddcutil and integrates with Home Assistant via MQTT.
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

# Path Flask reads for current monitor state
STATE_FILE = os.path.join(os.environ.get("ADDON_CONFIG_PATH", "/config"), "state.json")

# ==============================================================================
# Logging setup
# ==============================================================================

LOG_LEVEL_MAP = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
}

log_level_str = os.environ.get("ADDON_LOG_LEVEL", "info").lower()
logging.basicConfig(
    level=LOG_LEVEL_MAP.get(log_level_str, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ddcutil_addon")


# ==============================================================================
# Config
# ==============================================================================

@dataclass
class InputSource:
    vcp_value: int
    alias: str


@dataclass
class Config:
    log_level: str = "info"
    mqtt_enabled: bool = False
    mqtt_host: str = "core-mosquitto"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "ddcutil"
    mqtt_discovery: bool = True
    mqtt_discovery_prefix: str = "homeassistant"
    poll_enabled: bool = False
    poll_interval: int = 600
    input_sources: list[InputSource] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        raw_sources = os.environ.get("ADDON_INPUT_SOURCES", "[]")
        try:
            sources_data = json.loads(raw_sources) if raw_sources else []
        except json.JSONDecodeError:
            sources_data = []

        input_sources = [
            InputSource(vcp_value=s["vcp_value"], alias=s["alias"])
            for s in sources_data
            if "vcp_value" in s and "alias" in s
        ]

        return cls(
            log_level=os.environ.get("ADDON_LOG_LEVEL", "info"),
            mqtt_enabled=os.environ.get("ADDON_MQTT_ENABLED", "false").lower() == "true",
            mqtt_host=os.environ.get("ADDON_MQTT_HOST", "core-mosquitto"),
            mqtt_port=int(os.environ.get("ADDON_MQTT_PORT", "1883")),
            mqtt_username=os.environ.get("ADDON_MQTT_USERNAME", ""),
            mqtt_password=os.environ.get("ADDON_MQTT_PASSWORD", ""),
            mqtt_topic_prefix=os.environ.get("ADDON_MQTT_TOPIC_PREFIX", "ddcutil"),
            mqtt_discovery=os.environ.get("ADDON_MQTT_DISCOVERY", "true").lower() == "true",
            mqtt_discovery_prefix=os.environ.get("ADDON_MQTT_DISCOVERY_PREFIX", "homeassistant"),
            poll_enabled=os.environ.get("ADDON_POLL_ENABLED", "false").lower() == "true",
            poll_interval=int(os.environ.get("ADDON_POLL_INTERVAL", "600")),
            input_sources=input_sources,
        )


# ==============================================================================
# DDCUtil wrapper
# ==============================================================================

class DDCUtil:
    """Thin wrapper around the ddcutil CLI."""

    # VCP feature codes
    VCP_BRIGHTNESS = 0x10
    VCP_CONTRAST = 0x12
    VCP_INPUT_SOURCE = 0x60
    VCP_POWER = 0xD6

    # Power values
    POWER_ON = 1
    POWER_OFF = 5

    def __init__(self, bus: Optional[int] = None):
        self.bus = bus
        self._bus_flag = ["--bus", str(bus)] if bus is not None else []

    def _run(self, args: list[str]) -> tuple[bool, str]:
        """Run a ddcutil command. Returns (success, output)."""
        cmd = ["ddcutil"] + self._bus_flag + args
        log.debug("Running: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            log.warning("ddcutil error: %s", result.stderr.strip())
            return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            log.error("ddcutil command timed out: %s", " ".join(cmd))
            return False, "timeout"
        except FileNotFoundError:
            log.error("ddcutil not found. Is it installed?")
            return False, "not_found"

    def detect(self) -> Optional[dict]:
        """
        Detect connected monitor by scanning all available I2C buses.
        Dynamically finds the right bus — no hardcoded bus numbers needed.
        Returns monitor info dict or None.
        """
        # First try global detect (finds monitor on any bus)
        ok, output = self._run(["detect", "--brief"])
        if ok and output:
            monitor = self._parse_detect_output(output)
            if monitor:
                return monitor

        # If global detect fails, scan each bus individually
        log.debug("Global detect failed, scanning buses individually...")
        import glob
        buses = sorted([
            int(p.replace("/dev/i2c-", ""))
            for p in glob.glob("/dev/i2c-*")
        ])
        log.debug("Available I2C buses: %s", buses)

        for bus in buses:
            log.debug("Trying bus %d...", bus)
            cmd = ["ddcutil", "--bus", str(bus), "detect", "--brief"]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    monitor = self._parse_detect_output(result.stdout)
                    if monitor:
                        monitor["bus"] = bus
                        log.info("Monitor found on bus %d", bus)
                        return monitor
            except subprocess.TimeoutExpired:
                log.debug("Bus %d timed out", bus)
                continue

        return None

    def _parse_detect_output(self, output: str) -> Optional[dict]:
        """Parse ddcutil detect output into a monitor info dict."""
        monitor = {}
        for line in output.splitlines():
            line = line.strip()
            try:
                bus_match = re.search(r"I2C bus:\s+/dev/i2c-(\d+)", output)
                if bus_match:
                    monitor["bus"] = int(bus_match.group(1))
            except (AttributeError, ValueError):
                pass
            if "Monitor:" in line:
                monitor["name"] = line.split("Monitor:")[-1].strip()
            if "Model:" in line:
                monitor["model"] = line.split("Model:")[-1].strip()
            if "Manufacturer:" in line:
                monitor["manufacturer"] = line.split("Manufacturer:")[-1].strip()
        return monitor if monitor else None

    def get_capabilities(self) -> str:
        """Return raw capabilities string."""
        ok, output = self._run(["capabilities"])
        return output if ok else ""

    def get_vcp(self, feature: int) -> Optional[int]:
        """Get current value of a VCP feature."""
        ok, output = self._run(["getvcp", hex(feature)])
        if not ok:
            return None
        # Parse: "VCP code 0x10 (Brightness): current value = 75, max value = 100"
        match = re.search(r"current value\s*=\s*(\d+)", output)
        if match:
            return int(match.group(1))
        return None

    def set_vcp(self, feature: int, value: int) -> bool:
        """Set a VCP feature value.
        Uses --noverify to skip readback verification — required for monitors
        like Samsung Neo G9 that accept commands but return invalid responses
        during the verification step (DDCRC_VERIFY error).
        """
        ok, _ = self._run(["setvcp", hex(feature), str(value), "--noverify"])
        return ok

    def is_brightness_locked(self) -> bool:
        """
        Check if brightness control is locked by monitor features.
        On Samsung monitors, Eye Saver, HDR, Dynamic Contrast and Eco Saving
        modes lock brightness — VCP 0x10 becomes unreadable when any are active.
        """
        return self.get_brightness() is None

    def get_brightness(self) -> Optional[int]:
        return self.get_vcp(self.VCP_BRIGHTNESS)

    def set_brightness(self, value: int) -> bool:
        value = max(0, min(100, value))
        if self.is_brightness_locked():
            log.warning(
                "Brightness control is locked by monitor. "
                "Disable Eye Saver, HDR, Dynamic Contrast and "
                "Eco Saving modes in your monitor OSD settings."
            )
            return False
        return self.set_vcp(self.VCP_BRIGHTNESS, value)

    def get_contrast(self) -> Optional[int]:
        return self.get_vcp(self.VCP_CONTRAST)

    def set_contrast(self, value: int) -> bool:
        value = max(0, min(100, value))
        return self.set_vcp(self.VCP_CONTRAST, value)

    def get_input(self) -> Optional[int]:
        return self.get_vcp(self.VCP_INPUT_SOURCE)

    def set_input(self, vcp_value: int) -> bool:
        return self.set_vcp(self.VCP_INPUT_SOURCE, vcp_value)

    def get_power(self) -> Optional[str]:
        val = self.get_vcp(self.VCP_POWER)
        if val is None:
            return None
        return "ON" if val == self.POWER_ON else "OFF"

    def set_power(self, state: str) -> bool:
        value = self.POWER_ON if state.upper() == "ON" else self.POWER_OFF
        return self.set_vcp(self.VCP_POWER, value)

    def get_state(self) -> dict:
        """Read all controllable values in one pass."""
        brightness = self.get_brightness()
        return {
            "brightness": brightness,
            "brightness_locked": brightness is None,
            "contrast": self.get_contrast(),
            "input": self.get_input(),
            "power": self.get_power(),
        }


# ==============================================================================
# Capabilities dump (Option 1 + 2)
# ==============================================================================

def parse_input_sources_from_capabilities(capabilities: str) -> list[dict]:
    """Parse input source VCP values from capabilities string."""
    sources = []
    in_input_block = False

    for line in capabilities.splitlines():
        stripped = line.strip()
        if re.match(r"Feature:\s+60\s+\(Input Source\)", stripped, re.IGNORECASE):
            in_input_block = True
            continue
        if in_input_block:
            if stripped.startswith("Feature:"):
                break
            match = re.match(r"([0-9a-fA-F]+):\s+(.*)", stripped)
            if match:
                sources.append({
                    "vcp_value": int(match.group(1), 16),
                    "name": match.group(2).strip(),
                })

    return sources


def dump_capabilities(ddc: DDCUtil, monitor_info: dict, config: Config) -> None:
    """
    Option 1: Log capabilities to addon log.
    Option 2: Write capabilities.txt to addon_config path.
    """
    capabilities_raw = ddc.get_capabilities()
    input_sources = parse_input_sources_from_capabilities(capabilities_raw)

    # --- Option 1: Log output ---
    log.info("=" * 60)
    log.info("Monitor detected: %s", monitor_info.get("name", "Unknown"))
    if monitor_info.get("manufacturer"):
        log.info("Manufacturer: %s", monitor_info["manufacturer"])
    if monitor_info.get("model"):
        log.info("Model: %s", monitor_info["model"])
    log.info("-" * 60)

    if input_sources:
        log.info("Available input sources (use these in your config):")
        for src in input_sources:
            log.info("  VCP Value: %-5s → %s", src["vcp_value"], src["name"])
        log.info("")
        log.info("Example config.yaml input_sources:")
        log.info("  input_sources:")
        for src in input_sources:
            log.info("    - vcp_value: %s", src["vcp_value"])
            log.info('      alias: "%s"', src["name"])
    else:
        log.info("No input sources found in capabilities.")

    log.info("=" * 60)

    # --- Option 2: Write capabilities.txt ---
    config_path = os.environ.get("ADDON_CONFIG_PATH", "/config")
    output_path = os.path.join(config_path, "capabilities.txt")

    try:
        os.makedirs(config_path, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("DDC/CI Monitor Control - Capabilities Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"Monitor:      {monitor_info.get('name', 'Unknown')}\n")
            f.write(f"Manufacturer: {monitor_info.get('manufacturer', 'Unknown')}\n")
            f.write(f"Model:        {monitor_info.get('model', 'Unknown')}\n")
            f.write("=" * 60 + "\n\n")

            if input_sources:
                f.write("Available Input Sources\n")
                f.write("-" * 40 + "\n")
                f.write(f"{'VCP Value':<12} {'Name'}\n")
                f.write(f"{'-'*10:<12} {'-'*20}\n")
                for src in input_sources:
                    f.write(f"{src['vcp_value']:<12} {src['name']}\n")
                f.write("\n")
                f.write("Example input_sources config:\n")
                f.write("-" * 40 + "\n")
                f.write("input_sources:\n")
                for src in input_sources:
                    f.write(f"  - vcp_value: {src['vcp_value']}\n")
                f.write('    alias: "Your Alias Here"\n')
            else:
                f.write("No input sources detected.\n")

            f.write("\n")
            f.write("Full Capabilities\n")
            f.write("-" * 40 + "\n")
            f.write(capabilities_raw)

        log.info("Capabilities written to: %s", output_path)
    except OSError as e:
        log.warning("Could not write capabilities.txt: %s", e)


# ==============================================================================
# Atomic state file writer (Flask reads this — no race conditions)
# ==============================================================================

def write_state_atomic(data: dict) -> None:
    """
    Write state to STATE_FILE atomically using a temp file + os.replace().
    os.replace() is atomic on Linux — Flask always gets a complete file,
    never a partial write.
    """
    path = STATE_FILE
    dir_ = os.path.dirname(path)
    try:
        os.makedirs(dir_, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=dir_, delete=False, suffix=".tmp"
        ) as f:
            json.dump(data, f)
            tmp_path = f.name
        os.replace(tmp_path, path)
        log.debug("State file updated: %s", path)
    except OSError as e:
        log.warning("Could not write state file: %s", e)




class Topics:
    def __init__(self, prefix: str):
        self.prefix = prefix

    @property
    def state(self) -> str:
        return f"{self.prefix}/state"

    @property
    def availability(self) -> str:
        return f"{self.prefix}/availability"

    @property
    def brightness_set(self) -> str:
        return f"{self.prefix}/brightness/set"

    @property
    def contrast_set(self) -> str:
        return f"{self.prefix}/contrast/set"

    @property
    def input_set(self) -> str:
        return f"{self.prefix}/input/set"

    @property
    def power_set(self) -> str:
        return f"{self.prefix}/power/set"

    def all_command_topics(self) -> list[str]:
        return [
            self.brightness_set,
            self.contrast_set,
            self.input_set,
            self.power_set,
        ]


# ==============================================================================
# MQTT Discovery payloads
# ==============================================================================

def build_discovery_payloads(
    config: Config,
    topics: Topics,
    monitor_info: dict,
) -> list[tuple[str, dict]]:
    """Build HA MQTT discovery payloads. Returns list of (topic, payload)."""

    device = {
        "identifiers": ["ddcutil_monitor_1"],
        "name": monitor_info.get("name", "DDC/CI Monitor"),
        "model": monitor_info.get("model", "Unknown"),
        "manufacturer": monitor_info.get("manufacturer", "Unknown"),
        "sw_version": "1.0.0",
    }

    availability = {
        "topic": topics.availability,
        "payload_available": "online",
        "payload_not_available": "offline",
    }

    dp = config.mqtt_discovery_prefix
    payloads = []

    # Light entity (brightness + power)
    payloads.append((
        f"{dp}/light/ddcutil_monitor_1/config",
        {
            "name": "Brightness",
            "unique_id": "ddcutil_monitor_1_light",
            "device": device,
            "availability": availability,
            "schema": "json",
            "state_topic": topics.state,
            "command_topic": topics.brightness_set,
            "brightness": True,
            "brightness_scale": 100,
            "payload_on": "ON",
            "payload_off": "OFF",
            "optimistic": False,
        },
    ))

    # Contrast as number entity
    payloads.append((
        f"{dp}/number/ddcutil_monitor_1_contrast/config",
        {
            "name": "Contrast",
            "unique_id": "ddcutil_monitor_1_contrast",
            "device": device,
            "availability": availability,
            "state_topic": topics.state,
            "command_topic": topics.contrast_set,
            "value_template": "{{ value_json.contrast }}",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
        },
    ))

    # Input select entity
    if config.input_sources:
        input_options = [s.alias for s in config.input_sources]
    else:
        input_options = ["Unknown"]

    payloads.append((
        f"{dp}/select/ddcutil_monitor_1_input/config",
        {
            "name": "Input Source",
            "unique_id": "ddcutil_monitor_1_input",
            "device": device,
            "availability": availability,
            "state_topic": topics.state,
            "command_topic": topics.input_set,
            "value_template": "{{ value_json.input_alias }}",
            "options": input_options,
        },
    ))

    # Power switch
    payloads.append((
        f"{dp}/switch/ddcutil_monitor_1_power/config",
        {
            "name": "Power",
            "unique_id": "ddcutil_monitor_1_power",
            "device": device,
            "availability": availability,
            "state_topic": topics.state,
            "command_topic": topics.power_set,
            "value_template": "{{ value_json.power }}",
            "payload_on": "ON",
            "payload_off": "OFF",
        },
    ))

    return payloads


# ==============================================================================
# Main controller
# ==============================================================================

class MonitorController:
    def __init__(self, config: Config, ddc: DDCUtil, monitor_info: dict):
        self.config = config
        self.ddc = ddc
        self.monitor_info = monitor_info
        self.topics = Topics(config.mqtt_topic_prefix)
        self.mqtt_client: Optional[mqtt.Client] = None
        self._last_poll = 0.0

        # Build alias lookup maps
        self._vcp_to_alias: dict[int, str] = {
            s.vcp_value: s.alias for s in config.input_sources
        }
        self._alias_to_vcp: dict[str, int] = {
            s.alias: s.vcp_value for s in config.input_sources
        }

    def _resolve_input_alias(self, vcp_value: Optional[int]) -> str:
        if vcp_value is None:
            return "Unknown"
        return self._vcp_to_alias.get(vcp_value, f"Input {vcp_value}")

    def _publish_state(self) -> None:
        """Read monitor state, publish to MQTT and write atomic state file."""
        state = self.ddc.get_state()
        payload = {
            "brightness": state.get("brightness"),
            "brightness_locked": state.get("brightness_locked", False),
            "contrast": state.get("contrast"),
            "input": state.get("input"),
            "input_alias": self._resolve_input_alias(state.get("input")),
            "power": state.get("power") or "OFF",
            "state": "ON" if state.get("power") == "ON" else "OFF",
            "monitor": self.monitor_info,
            "input_sources": [
                {"vcp_value": s.vcp_value, "alias": s.alias}
                for s in self.config.input_sources
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Always write state file (Flask reads this)
        write_state_atomic(payload)

        # Publish to MQTT only if connected
        if self.mqtt_client:
            self.mqtt_client.publish(
                self.topics.state,
                json.dumps(payload),
                retain=True,
            )
        log.debug("State updated: %s", payload)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Connected to MQTT broker at %s:%s", self.config.mqtt_host, self.config.mqtt_port)
            client.publish(self.topics.availability, "online", retain=True)

            # Subscribe to all command topics
            for topic in self.topics.all_command_topics():
                client.subscribe(topic)
                log.debug("Subscribed to: %s", topic)

            # Publish discovery payloads
            if self.config.mqtt_discovery:
                for disc_topic, payload in build_discovery_payloads(
                    self.config, self.topics, self.monitor_info
                ):
                    client.publish(disc_topic, json.dumps(payload), retain=True)
                    log.debug("Published discovery: %s", disc_topic)
                log.info("MQTT discovery payloads published.")

            # Publish initial state
            self._publish_state()
        else:
            log.error("Failed to connect to MQTT broker. Return code: %s", rc)

    def _on_disconnect(self, client, userdata, rc):
        log.warning("Disconnected from MQTT broker (rc=%s). Reconnecting...", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8").strip()
        log.info("Received command: %s → %s", topic, payload)

        success = False

        if topic == self.topics.brightness_set:
            try:
                # Payload can be plain int or JSON with brightness key
                value = int(json.loads(payload).get("brightness", payload)) if payload.startswith("{") else int(payload)
                success = self.ddc.set_brightness(value)
            except (ValueError, KeyError):
                log.error("Invalid brightness payload: %s", payload)

        elif topic == self.topics.contrast_set:
            try:
                success = self.ddc.set_contrast(int(payload))
            except ValueError:
                log.error("Invalid contrast payload: %s", payload)

        elif topic == self.topics.input_set:
            # Payload is an alias string
            vcp = self._alias_to_vcp.get(payload)
            if vcp is not None:
                success = self.ddc.set_input(vcp)
            else:
                log.error("Unknown input alias: '%s'. Check your input_sources config.", payload)

        elif topic == self.topics.power_set:
            if payload.upper() in ("ON", "OFF"):
                success = self.ddc.set_power(payload.upper())
            else:
                log.error("Invalid power payload: %s (expected ON or OFF)", payload)

        if success:
            # Small delay to let monitor apply the change before reading back
            time.sleep(0.5)
            self._publish_state()
        else:
            log.warning("Command failed for topic: %s", topic)

    def _setup_mqtt(self) -> bool:
        """Set up and connect MQTT client."""
        client = mqtt.Client(client_id="ddcutil_addon", clean_session=True)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

        if self.config.mqtt_username:
            client.username_pw_set(
                self.config.mqtt_username,
                self.config.mqtt_password or None,
            )

        # Set LWT so HA knows if the add-on dies
        client.will_set(self.topics.availability, "offline", retain=True)

        try:
            client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
            self.mqtt_client = client
            return True
        except Exception as e:
            log.error("Could not connect to MQTT broker: %s", e)
            return False

    def run(self) -> None:
        """Main run loop."""
        if self.config.mqtt_enabled:
            if not self._setup_mqtt():
                log.error("MQTT setup failed. Running in shell-command mode only.")
            else:
                self.mqtt_client.loop_start()

        log.info("DDC/CI Monitor Control is running.")

        if not self.config.mqtt_enabled:
            log.info("MQTT is disabled. Add-on is available for shell commands only.")
            log.info("Example: docker exec addon_ddcutil ddcutil setvcp 0x10 80")

        try:
            while True:
                # Optional slow polling
                if (
                    self.config.poll_enabled
                    and self.mqtt_client
                    and time.time() - self._last_poll >= self.config.poll_interval
                ):
                    log.debug("Polling monitor state...")
                    self._publish_state()
                    self._last_poll = time.time()

                time.sleep(5)

        except KeyboardInterrupt:
            log.info("Shutting down...")
        finally:
            if self.mqtt_client:
                self.mqtt_client.publish(self.topics.availability, "offline", retain=True)
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()


# ==============================================================================
# Entry point
# ==============================================================================

def main() -> None:
    config = Config.from_env()
    ddc = DDCUtil()

    log.info("Detecting monitor...")
    monitor_info = ddc.detect()

    if not monitor_info:
        log.error("No monitor detected via DDC/CI.")
        log.error("Check your cable supports DDC/CI and the monitor has it enabled.")
        log.error("Try: ddcutil detect --verbose")
        sys.exit(1)

    log.info("Monitor detected: %s", monitor_info.get("name", "Unknown"))

    # Set bus explicitly if detected
    if "bus" in monitor_info:
        ddc.bus = monitor_info["bus"]
        ddc._bus_flag = ["--bus", str(monitor_info["bus"])]

    # Dump capabilities (Option 1 log + Option 2 file)
    dump_capabilities(ddc, monitor_info, config)

    # Write initial state file so Flask has something to show immediately
    write_state_atomic({
        "brightness": None,
        "contrast": None,
        "input": None,
        "input_alias": "Unknown",
        "power": "Unknown",
        "state": "Unknown",
        "monitor": monitor_info,
        "input_sources": [
            {"vcp_value": s.vcp_value, "alias": s.alias}
            for s in config.input_sources
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "starting",
    })

    # Start controller
    controller = MonitorController(config, ddc, monitor_info)
    controller.run()


if __name__ == "__main__":
    main()
