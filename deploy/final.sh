#!/bin/bash
# FINAL - Návrat k fungujúcej verzii z 27.3. + XLSX
D="$(cd "$(dirname "$0")" && pwd)"
BK="/config/backups/final_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/packages" "$BK/scripts"
cp /config/packages/ev_charging_tracking.yaml "$BK/packages/" 2>/dev/null
cp /config/scripts/log_ev_session.sh "$BK/scripts/" 2>/dev/null
cp /config/scripts/ev_generate_report.py "$BK/scripts/" 2>/dev/null
echo "✅ Záloha: $BK"

cp "$D/ev_charging_tracking.yaml" /config/packages/ && echo "✅ ev_charging_tracking.yaml"
cp "$D/log_ev_session.sh" /config/scripts/ && chmod +x /config/scripts/log_ev_session.sh && echo "✅ log_ev_session.sh"
cp "$D/ev_generate_report.py" /config/scripts/ && echo "✅ ev_generate_report.py"

pip3 install openpyxl --break-system-packages -q 2>/dev/null
python3 -c "import openpyxl; print('✅ openpyxl OK')" 2>/dev/null

# Test XLSX hneď
python3 /config/scripts/ev_generate_report.py xlsx 2>&1 && echo "✅ XLSX vygenerovaný"

echo ""
echo "✅ Reštartuj HA."
echo "ROLLBACK: cp $BK/packages/ev_charging_tracking.yaml /config/packages/ && cp $BK/scripts/log_ev_session.sh /config/scripts/"
