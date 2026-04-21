"""
DDC/CI Monitor Control - Web UI (v1.1, read-only)
Served via Home Assistant ingress. Reads state.json written atomically
by ddcutil_mqtt.py — no race conditions.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string

# ==============================================================================
# Config
# ==============================================================================

CONFIG_PATH = os.environ.get("ADDON_CONFIG_PATH", "/config")
STATE_FILE = os.path.join(CONFIG_PATH, "state.json")
CAPABILITIES_FILE = os.path.join(CONFIG_PATH, "capabilities.txt")
INGRESS_PATH = os.environ.get("INGRESS_PATH", "")
PORT = int(os.environ.get("ADDON_WEB_PORT", "8099"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ddcutil_web")

app = Flask(__name__)


# ==============================================================================
# Helpers
# ==============================================================================

def read_state() -> dict:
    """Read state.json. Always returns a valid dict."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"status": "waiting", "monitor": {}}
    except json.JSONDecodeError:
        return {"status": "error", "monitor": {}}


def read_capabilities() -> str:
    """Read capabilities.txt raw content."""
    try:
        return Path(CAPABILITIES_FILE).read_text()
    except FileNotFoundError:
        return "Capabilities not yet available. Start the add-on and check again."


def time_ago(iso_string: str) -> str:
    """Convert ISO timestamp to human-readable 'X seconds ago'."""
    try:
        dt = datetime.fromisoformat(iso_string)
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        return f"{seconds // 3600}h ago"
    except Exception:
        return "unknown"


# ==============================================================================
# HTML template (inline — no templates/ folder needed)
# ==============================================================================

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DDC/CI Monitor Control</title>
  <style>
    :root {
      --bg: #111318;
      --surface: #1c1f26;
      --surface2: #252930;
      --border: #2e3340;
      --accent: #4f8ef7;
      --accent-dim: #1e3a6e;
      --text: #e2e5ed;
      --text-dim: #7a8099;
      --green: #4caf82;
      --red: #e05c5c;
      --yellow: #f0b429;
      --radius: 10px;
      --font: "Inter", "Segoe UI", system-ui, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      font-size: 14px;
      line-height: 1.6;
      padding: 24px;
      max-width: 860px;
      margin: 0 auto;
    }

    /* ── Header ── */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 28px;
      flex-wrap: wrap;
      gap: 12px;
    }
    .header h1 {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.3px;
    }
    .header h1 span {
      color: var(--accent);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 99px;
      font-size: 12px;
      font-weight: 500;
    }
    .badge-online  { background: rgba(76,175,130,0.15); color: var(--green); }
    .badge-waiting { background: rgba(240,180,41,0.15);  color: var(--yellow); }
    .badge-error   { background: rgba(224,92,92,0.15);   color: var(--red); }
    .badge::before {
      content: "";
      width: 7px; height: 7px;
      border-radius: 50%;
      background: currentColor;
    }

    /* ── Cards ── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 24px;
      margin-bottom: 16px;
    }
    .card-title {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: var(--text-dim);
      margin-bottom: 16px;
    }

    /* ── Monitor info grid ── */
    .info-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
    }
    .info-item label {
      display: block;
      font-size: 11px;
      color: var(--text-dim);
      margin-bottom: 3px;
    }
    .info-item value {
      display: block;
      font-size: 15px;
      font-weight: 500;
    }

    /* ── State gauges ── */
    .state-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 12px;
    }
    .gauge {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
    }
    .gauge-label {
      font-size: 11px;
      color: var(--text-dim);
      margin-bottom: 6px;
    }
    .gauge-value {
      font-size: 24px;
      font-weight: 700;
      color: var(--accent);
    }
    .gauge-value.power-on  { color: var(--green); }
    .gauge-value.power-off { color: var(--red); }
    .gauge-value.unknown   { color: var(--text-dim); font-size: 16px; }
    .gauge-bar {
      height: 4px;
      background: var(--border);
      border-radius: 2px;
      margin-top: 8px;
      overflow: hidden;
    }
    .gauge-bar-fill {
      height: 100%;
      background: var(--accent);
      border-radius: 2px;
      transition: width 0.4s ease;
    }

    /* ── Input sources table ── */
    table {
      width: 100%;
      border-collapse: collapse;
    }
    thead th {
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      color: var(--text-dim);
      padding: 0 12px 10px 0;
      border-bottom: 1px solid var(--border);
    }
    tbody td {
      padding: 10px 12px 10px 0;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }
    tbody tr:last-child td { border-bottom: none; }
    .vcp-chip {
      display: inline-block;
      background: var(--accent-dim);
      color: var(--accent);
      border-radius: 4px;
      padding: 2px 8px;
      font-size: 12px;
      font-family: monospace;
      font-weight: 600;
    }
    .active-input {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(76,175,130,0.1);
      color: var(--green);
      border-radius: 4px;
      padding: 2px 8px;
      font-size: 12px;
    }
    .active-input::before {
      content: "";
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--green);
    }

    /* ── Capabilities raw block ── */
    .capabilities-toggle {
      background: none;
      border: 1px solid var(--border);
      color: var(--text-dim);
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 12px;
      cursor: pointer;
      margin-bottom: 14px;
      transition: border-color 0.2s, color 0.2s;
    }
    .capabilities-toggle:hover {
      border-color: var(--accent);
      color: var(--text);
    }
    .capabilities-raw {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      font-family: monospace;
      font-size: 12px;
      color: var(--text-dim);
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 320px;
      overflow-y: auto;
      display: none;
    }
    .capabilities-raw.open { display: block; }

    /* ── Footer ── */
    .footer {
      margin-top: 28px;
      font-size: 12px;
      color: var(--text-dim);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }
    .footer a {
      color: var(--accent);
      text-decoration: none;
    }

    /* ── Empty state ── */
    .empty {
      text-align: center;
      padding: 40px 0;
      color: var(--text-dim);
    }
    .empty-icon { font-size: 40px; margin-bottom: 12px; }

    /* ── Refresh button ── */
    .refresh-btn {
      background: var(--accent-dim);
      border: 1px solid var(--accent);
      color: var(--accent);
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.2s;
    }
    .refresh-btn:hover { background: var(--accent); color: #fff; }
  </style>
</head>
<body>

<div class="header">
  <h1>DDC/CI <span>Monitor Control</span></h1>
  <div style="display:flex;gap:10px;align-items:center;">
    {% if status == "waiting" %}
      <span class="badge badge-waiting">Starting…</span>
    {% elif status == "error" %}
      <span class="badge badge-error">Error</span>
    {% else %}
      <span class="badge badge-online">Online</span>
    {% endif %}
    <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
  </div>
</div>

{% if status in ("waiting", "error") %}
  <div class="card">
    <div class="empty">
      <div class="empty-icon">🖥️</div>
      <p>
        {% if status == "waiting" %}
          Waiting for monitor detection… Start the add-on and refresh in a moment.
        {% else %}
          Could not read monitor state. Check the add-on log for errors.
        {% endif %}
      </p>
    </div>
  </div>

{% else %}

  <!-- Monitor Info -->
  <div class="card">
    <div class="card-title">Monitor</div>
    <div class="info-grid">
      <div class="info-item">
        <label>Name</label>
        <value>{{ monitor.get("name", "Unknown") }}</value>
      </div>
      <div class="info-item">
        <label>Manufacturer</label>
        <value>{{ monitor.get("manufacturer", "Unknown") }}</value>
      </div>
      <div class="info-item">
        <label>Model</label>
        <value>{{ monitor.get("model", "Unknown") }}</value>
      </div>
      <div class="info-item">
        <label>I2C Bus</label>
        <value>/dev/i2c-{{ monitor.get("bus", "?") }}</value>
      </div>
    </div>
  </div>

  <!-- Current State -->
  <div class="card">
    <div class="card-title">Current State
      <span style="font-weight:400;text-transform:none;letter-spacing:0;margin-left:8px;">
        — updated {{ updated_ago }}
      </span>
    </div>
    <div class="state-grid">

      <div class="gauge">
        <div class="gauge-label">Brightness</div>
        {% if brightness is not none %}
          <div class="gauge-value">{{ brightness }}%</div>
          <div class="gauge-bar">
            <div class="gauge-bar-fill" style="width:{{ brightness }}%"></div>
          </div>
        {% else %}
          <div class="gauge-value unknown">—</div>
        {% endif %}
      </div>

      <div class="gauge">
        <div class="gauge-label">Contrast</div>
        {% if contrast is not none %}
          <div class="gauge-value">{{ contrast }}%</div>
          <div class="gauge-bar">
            <div class="gauge-bar-fill" style="width:{{ contrast }}%"></div>
          </div>
        {% else %}
          <div class="gauge-value unknown">—</div>
        {% endif %}
      </div>

      <div class="gauge">
        <div class="gauge-label">Input</div>
        <div class="gauge-value" style="font-size:16px;">{{ input_alias }}</div>
      </div>

      <div class="gauge">
        <div class="gauge-label">Power</div>
        {% if power == "ON" %}
          <div class="gauge-value power-on">ON</div>
        {% elif power == "OFF" %}
          <div class="gauge-value power-off">OFF</div>
        {% else %}
          <div class="gauge-value unknown">—</div>
        {% endif %}
      </div>

    </div>
  </div>

  <!-- Input Source Map -->
  <div class="card">
    <div class="card-title">Input Sources</div>
    {% if input_sources %}
      <table>
        <thead>
          <tr>
            <th>VCP Value</th>
            <th>Alias</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {% for src in input_sources %}
          <tr>
            <td><span class="vcp-chip">{{ src.vcp_value }}</span></td>
            <td>{{ src.alias }}</td>
            <td>
              {% if src.vcp_value == current_input %}
                <span class="active-input">Active</span>
              {% else %}
                <span style="color:var(--text-dim);font-size:12px;">—</span>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p style="color:var(--text-dim);">
        No input source aliases configured. Check the <strong>capabilities.txt</strong>
        file in your addon_configs folder and add them to your add-on config.
      </p>
    {% endif %}
  </div>

  <!-- Capabilities -->
  <div class="card">
    <div class="card-title">Full Capabilities</div>
    <button class="capabilities-toggle" onclick="toggleCaps(this)">
      Show raw capabilities
    </button>
    <pre class="capabilities-raw" id="caps">{{ capabilities }}</pre>
  </div>

{% endif %}

<div class="footer">
  <span>DDC/CI Monitor Control v1.1</span>
  <span>
    <a href="https://github.com/YOUR_USERNAME/addon-ddcutil" target="_blank">
      GitHub
    </a>
    &nbsp;·&nbsp;
    <a href="https://community.home-assistant.io" target="_blank">
      Community
    </a>
  </span>
</div>

<script>
  function toggleCaps(btn) {
    const el = document.getElementById("caps");
    const open = el.classList.toggle("open");
    btn.textContent = open ? "Hide raw capabilities" : "Show raw capabilities";
  }

  // Auto-refresh every 30 seconds
  setTimeout(() => location.reload(), 30000);
</script>

</body>
</html>
"""


# ==============================================================================
# Routes
# ==============================================================================

@app.route("/")
def index():
    state = read_state()
    status = state.get("status", "online")

    # If state.json exists but has no status key it means we're running normally
    if "brightness" in state and "status" not in state:
        status = "online"

    return render_template_string(
        HTML,
        status=status,
        monitor=state.get("monitor", {}),
        brightness=state.get("brightness"),
        contrast=state.get("contrast"),
        input_alias=state.get("input_alias", "Unknown"),
        current_input=state.get("input"),
        power=state.get("power", "Unknown"),
        input_sources=state.get("input_sources", []),
        capabilities=read_capabilities(),
        updated_ago=time_ago(state.get("updated_at", "")),
    )


@app.route("/api/state")
def api_state():
    """JSON endpoint — useful for debugging or future interactive controls."""
    return jsonify(read_state())


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    log.info("Starting DDC/CI Monitor Control web UI on port %s", PORT)
    log.info("State file: %s", STATE_FILE)
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )
