#!/usr/bin/env bash
# Serve the bundle the Docker image serves.
#
# `next start` is not supported with output: "standalone" — Next says so out
# loud ("next start does not work with output: standalone configuration") and
# today it still serves anyway. Building CI on a warning like that means the
# day Next makes it a hard error, the failure lands in the e2e job with no
# obvious connection to the image. So CI runs what production runs.
#
# Usage: scripts/serve-standalone.sh [port]
set -euo pipefail

PORT="${1:-3000}"
DIST="${NEXT_DIST_DIR:-.next}"
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend" && pwd)"

if [ ! -d "$DIST/standalone" ]; then
    echo "$DIST/standalone does not exist — run 'npm run build' first." >&2
    exit 1
fi

# The same two directories frontend/Dockerfile copies into its runtime stage.
# `output: standalone` leaves static out on purpose, because Next expects a CDN
# to serve it; there is no CDN in compose and none here.
rm -rf "$DIST/standalone/$DIST/static"
cp -R "$DIST/static" "$DIST/standalone/$DIST/static"
# There is no frontend/public today; `set -e` would turn a bare test into an exit.
if [ -d public ]; then cp -R public "$DIST/standalone/public"; fi

exec env PORT="$PORT" HOSTNAME=127.0.0.1 NODE_ENV=production node "$DIST/standalone/server.js"
