#!/bin/bash
# ==============================================================================
# Script Name:   launch-netbox.sh
# Description:   Implementation and logic for launch-netbox.
# Author:        Mai Tan Duc <ducmai.network@gmail.com>
# Created:       2026-10-10
# Version:       1.0.0
# License:       MIT
# ==============================================================================
# Usage:         ./launch-netbox.sh [options] [arguments]
# Notes:         Automated bash utility script
# ==============================================================================

export GRANIAN_PORT=${GRANIAN_PORT:-8080}
export GRANIAN_WORKERS=${GRANIAN_WORKERS:-4}

exec granian \
  --host "::" \
  --interface "wsgi" \
  --no-ws \
  --respawn-failed-workers \
  --loop "uvloop" \
  --log \
  --log-level "info" \
  --access-log \
  --working-dir "/opt/netbox/netbox/" \
  --static-path-route "/static" \
  --static-path-mount "/opt/netbox/netbox/static/" \
  --static-path-dir-to-file index.html \
  --pid-file "/tmp/granian.pid" \
  "${GRANIAN_EXTRA_ARGS[@]}" \
  "netbox.granian:application"
