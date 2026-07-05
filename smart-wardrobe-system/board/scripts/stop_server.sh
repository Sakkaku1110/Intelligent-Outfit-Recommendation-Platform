#!/bin/bash
set -e

pkill -f "python3 -m app.server" || true
echo "Smart wardrobe server stopped if it was running."

