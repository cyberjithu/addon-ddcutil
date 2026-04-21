#!/usr/bin/with-contenv bashio

# ==============================================================================
# DDC/CI Monitor Control - Add-on entrypoint
# ==============================================================================

bashio::log.info "Starting DDC/CI Monitor Control..."

# ------------------------------------------------------------------------------
# Verify I2C devices are available
# ------------------------------------------------------------------------------
if ! ls /dev/i2c-* > /dev/null 2>&1; then
    bashio::log.fatal "No I2C devices found (/dev/i2c-* missing)!"
    bashio::log.fatal "Please ensure I2C is enabled on your system."
    bashio::log.fatal "See the documentation (DOCS.md) for instructions."
    bashio::exit.nok
fi

bashio::log.info "I2C devices found: $(ls /dev/i2c-* | tr '\n' ' ')"

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

# Pass input_sources as JSON string
export ADDON_INPUT_SOURCES=$(bashio::config 'input_sources')

# ------------------------------------------------------------------------------
# Resolve addon_config output directory
# ------------------------------------------------------------------------------
export ADDON_CONFIG_PATH="/config"
bashio::log.info "Capabilities will be written to: ${ADDON_CONFIG_PATH}/capabilities.txt"

# ------------------------------------------------------------------------------
# Launch Python core
# ------------------------------------------------------------------------------
bashio::log.info "Launching DDC/CI Monitor Control core..."
exec python3 /ddcutil_mqtt.py
