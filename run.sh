#!/bin/sh
# Usage: ./run.sh [options] <server_ip> <server_port>
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 main.py "$@"; fi
exec python main.py "$@"
