#!/bin/bash
# Exportuje dashboard z .storage do trackovaného súboru
mkdir -p /config/dashboards

# Default dashboard
if [ -f /config/.storage/lovelace ]; then
  cp /config/.storage/lovelace /config/dashboards/lovelace_default.json
fi

# Všetky custom dashboards
for f in /config/.storage/lovelace.*; do
  [ -f "$f" ] && cp "$f" /config/dashboards/$(basename "$f").json
done

echo "✅ Dashboards exported"
