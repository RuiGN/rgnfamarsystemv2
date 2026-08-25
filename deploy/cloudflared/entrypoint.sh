#!/bin/sh
set -e

if [ -f /run/secrets/CLOUDFLARE_TUNNEL_TOKEN ]; then
    export TUNNEL_TOKEN="$(cat /run/secrets/CLOUDFLARE_TUNNEL_TOKEN)"
fi

exec /usr/local/bin/cloudflared "$@"
