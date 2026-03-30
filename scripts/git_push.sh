#!/bin/bash
cd /config
git add -A
MSG="${1:-auto update $(date +%Y-%m-%d_%H:%M)}"
git commit -m "$MSG"
git push origin main
echo "✅ Pushed: $MSG"
