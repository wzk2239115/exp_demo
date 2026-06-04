#!/bin/bash
# Build statically linked socat and netcat-openbsd using Docker Alpine.
#
# Outputs:
#   data/server/socat   – static socat binary
#   data/runtime/nc     – static netcat (OpenBSD) binary
#
# Usage (from project root):
#   bash scripts/setup/static_build_socat.sh

set -euo pipefail

SOCAT_VERSION=${SOCAT_VERSION:-1.8.1.1}
NC_VERSION=${NC_VERSION:-debian/1.234-2}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APORTS_REF=v3.23.4

SOCAT_OUT="$PROJECT_ROOT/data/server"
NC_OUT="$PROJECT_ROOT/data/runtime"

mkdir -p "$SOCAT_OUT" "$NC_OUT"

echo "==> Building static socat ${SOCAT_VERSION} and netcat-openbsd ${NC_VERSION} via Docker Alpine..."

docker run --rm \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    -v "$SOCAT_OUT:/out/server" \
    -v "$NC_OUT:/out/runtime" \
    alpine:latest sh -c '
        set -eux

        apk add --no-cache \
            gcc musl-dev make wget linux-headers \
            git quilt libbsd-dev libbsd-static libmd-dev \
            openssl-dev openssl-libs-static zlib-static

        # ── Build static socat ──
        cd /tmp
        wget -q http://www.dest-unreach.org/socat/download/socat-'"${SOCAT_VERSION}"'.tar.gz
        tar xf socat-'"${SOCAT_VERSION}"'.tar.gz
        cd socat-'"${SOCAT_VERSION}"'
        CFLAGS="-O2 -static" LDFLAGS="-static" ./configure
        make -j$(nproc)
        install -m 755 socat /out/server/socat
        echo "    socat installed"

        # ── Build static netcat-openbsd ──
        cd /tmp
        git clone --depth 1 --branch '"${NC_VERSION}"' \
            https://salsa.debian.org/debian/netcat-openbsd.git
        cd netcat-openbsd

        export QUILT_PATCHES=debian/patches
        quilt push -a

        # Patch base64
        wget https://gitlab.alpinelinux.org/alpine/aports/-/raw/'"${APORTS_REF}"'/main/netcat-openbsd/base64.c
        wget https://gitlab.alpinelinux.org/alpine/aports/-/raw/'"${APORTS_REF}"'/main/netcat-openbsd/b64.patch
        patch -p1 < b64.patch
        sed -i '\''/^SRCS=/ s/$/ base64.c/'\'' Makefile

        make CFLAGS="-O2 -static" LDFLAGS="-static" LIBS="-lbsd -lmd"
        install -m 755 nc /out/runtime/nc
        echo "    nc installed"

        # Fix ownership to match the host user
        chown "$HOST_UID:$HOST_GID" /out/server/socat /out/runtime/nc
    '

echo "==> Done"
echo "    socat: $SOCAT_OUT/socat"
echo "    nc:    $NC_OUT/nc"
