#!/bin/bash
set -e

cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python3 -m app.server --host 0.0.0.0 --port "${SMART_WARDROBE_PORT:-8000}" --also-port "${SMART_WARDROBE_ALSO_PORT:-80}" --seed
