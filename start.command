#!/bin/bash
# Double-click in Finder to start the dev server (requires Python 3.11+).
cd "$(dirname "$0")"
chmod +x scripts/run.sh scripts/install.sh 2>/dev/null || true
exec ./scripts/run.sh
