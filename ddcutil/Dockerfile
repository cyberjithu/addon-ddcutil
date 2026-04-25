# ==============================================================================
# DDC/CI Monitor Control — Multi-stage Dockerfile
#
# Stage 1 (builder): Installs ddcutil from Alpine edge + Python packages.
#                    This stage is discarded — nothing leaks to the final image
#                    except what we explicitly COPY.
#
# Stage 2 (runtime): Minimal image with only runtime dependencies.
#                    No pip, no build tools, no apk cache.
# ==============================================================================

ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM ${BUILD_FROM} AS builder

# ddcutil 2.2.6+ lives in Alpine edge community.
# It fixes EPERM on /dev/i2c devices that plagued older versions on RPi4
# with the vc4-kms-v3d driver.
RUN apk add --no-cache \
    ddcutil \
    py3-pip \
    python3

# Install Python packages into /usr/local so they land on Python's
# default sys.path in the runtime stage without any PYTHONPATH tricks.
RUN pip3 install --no-cache-dir \
    --target=/python-packages \
    paho-mqtt==1.6.1 \
    flask==3.0.3

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Runtime dependencies only — no build tools, no pip.
# Packages confirmed against Alpine edge package index:
#   glib          → libglib-2.0.so.0  (ddcutil dep)
#   jansson       → libjansson.so.4   (ddcutil dep)
#   libudev-zero  → libudev.so.1      (ddcutil dep)
#   libusb        → libusb-1.0.so.0   (ddcutil dep)
#   libx11        → libX11.so.6       (ddcutil 2.2.6+ dep)
#   libxext       → libXext.so.6      (ddcutil 2.2.6+ dep)
#   libxrandr     → libXrandr.so.2    (ddcutil 2.2.6+ dep)
#   libdrm        → libdrm.so.2       (ddcutil 2.2.6+ dep)
#   i2c-tools     → i2cdetect for diagnostics
#   python3 + py3-pip → install packages then remove pip after
RUN apk add --no-cache \
    glib \
    jansson \
    libudev-zero \
    libusb \
    libx11 \
    libxext \
    libxrandr \
    libdrm \
    i2c-tools \
    python3 \
    py3-pip \
    && pip3 install --no-cache-dir --break-system-packages \
        paho-mqtt==1.6.1 \
        flask==3.0.3 \
    && apk del py3-pip \
    && rm -rf /root/.cache

# Copy ddcutil binary and its shared library from builder stage
COPY --from=builder /usr/bin/ddcutil        /usr/bin/ddcutil
COPY --from=builder /usr/lib/libddcutil.so* /usr/lib/

# Add-on source files
COPY run.sh          /
COPY ddcutil_mqtt.py /
COPY web.py          /

RUN chmod a+x /run.sh

LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="Jithu <cyberjithu@users.noreply.github.com>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Jithu" \
    org.opencontainers.image.authors="Jithu <cyberjithu@users.noreply.github.com>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

CMD ["/run.sh"]