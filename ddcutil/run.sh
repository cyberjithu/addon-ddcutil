#!/usr/bin/with-contenv bashio

# ==============================================================================
# DDC/CI Monitor Control - Add-on entrypoint
# ==============================================================================

bashio::log.info "Starting DDC/CI Monitor Control..."

# ------------------------------------------------------------------------------
# Dynamically fix permissions on all present I2C devices
# HA passes devices into the container but they may not be rw by default
# ------------------------------------------------------------------------------
bashio::log.info "Scanning for I2C devices..."

FOUND_I2C=false
for dev in /dev/i2c-*; do
    if [ -e "$dev" ]; then
        chmod a+rw "$dev" 2>/dev/null && \
        bashio::log.info "I2C device enabled: ${dev}"
        FOUND_I2C=true
    fi
done

# Fix permissions on any extra user-defined buses
for bus in $(bashio::config 'extra_i2c_buses'); do
    dev="/dev/i2c-${bus}"
    if [ -e "$dev" ]; then
        chmod a+rw "$dev" 2>/dev/null
        bashio::log.info "Extra I2C device enabled: ${dev}"
        FOUND_I2C=true
    else
        bashio::log.warning "Extra I2C device not found: ${dev} (bus ${bus} may not exist on this system)"
    fi
done

if [ "$FOUND_I2C" = false ]; then
    bashio::log.fatal "No I2C devices found!"
    bashio::log.fatal "Please ensure I2C is enabled on your system."
    bashio::log.fatal "See the documentation for instructions."
    bashio::log.fatal "If your bus number is above 12, add it to 'Extra I2C Bus Numbers' in the add-on config."
    bashio::exit.nok
fi

# ------------------------------------------------------------------------------
# Export config as environment variables for Python
# ------------------------------------------------------------------------------
export ADDON_LOG_LEVEL=$(bashio::config 'log_level')
export ADDON_MQTT_ENABLED=$(bashio::config 'mqtt_enabled')
export ADDON_MQTT_HOST=$(bashio::config 'mqtt_host')
export ADDON_MQTT_PORT=$(bashio::config 'mqtt_port')
export ADDON_MQTT_USERNAME=$(bashio::config 'mqtt_username')
export ADDON_MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export ADDON_MQTT_TOPIC_PREFIX=$(bashio::config 'mqtt_topic_prefix')
export ADDON_MQTT_DISCOVERY=$(bashio::config 'mqtt_discovery')
export ADDON_MQTT_DISCOVERY_PREFIX=$(bashio::config 'mqtt_discovery_prefix')
export ADDON_POLL_ENABLED=$(bashio::config 'poll_enabled')
export ADDON_POLL_INTERVAL=$(bashio::config 'poll_interval')
export ADDON_INPUT_SOURCES=$(bashio::config 'input_sources')

# ------------------------------------------------------------------------------
# Resolve paths
# ------------------------------------------------------------------------------
export ADDON_CONFIG_PATH="/config"
export ADDON_WEB_PORT="8099"

bashio::log.info "State file: ${ADDON_CONFIG_PATH}/state.json"
bashio::log.info "Capabilities file: ${ADDON_CONFIG_PATH}/capabilities.txt"

# ------------------------------------------------------------------------------
# Launch Flask web UI in background
# ------------------------------------------------------------------------------
bashio::log.info "Starting web UI on port ${ADDON_WEB_PORT}..."
python3 /web.py &
WEB_PID=$!
bashio::log.info "Web UI started (PID: ${WEB_PID})"

# ------------------------------------------------------------------------------
# Launch DDC/CI core (foreground — keeps the container alive)
# If the core dies, kill the web UI too so the supervisor restarts everything
# ------------------------------------------------------------------------------
bashio::log.info "Launching DDC/CI core..."
python3 /ddcutil_mqtt.py
CORE_EXIT=$?

bashio::log.warning "DDC/CI core exited (code: ${CORE_EXIT}). Shutting down web UI..."
kill "${WEB_PID}" 2>/dev/null
exit "${CORE_EXIT}"
