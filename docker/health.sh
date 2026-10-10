#!/bin/bash
# ==============================================================================
# Script Name:   health.sh
# Description:   Implementation and logic for health.
# Author:        Mai Tan Duc <ducmai.network@gmail.com>
# Created:       2026-10-10
# Version:       1.0.0
# License:       MIT
# ==============================================================================
# Usage:         ./health.sh [options] [arguments]
# Notes:         Automated bash utility script
# ==============================================================================

export CHECK_PORT=${GRANIAN_PORT:-8080}
curl -sf "http://localhost:${CHECK_PORT}/login/" >/dev/null || exit 1
