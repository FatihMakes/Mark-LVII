#!/usr/bin/env bash
# Runner script for JARVIS on macOS
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -d "$DIR/.venv" ]; then
    PYTHON="$DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "❌ Python 3 not found!"
    exit 1
fi

echo "🚀 Starting JARVIS Mark-LVII..."
"$PYTHON" main.py "$@"
