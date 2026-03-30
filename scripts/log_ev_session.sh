#!/bin/bash
# EV Session Logger v2 - 12 stlpcov (s prebytkami)
# Ulozit do: /config/scripts/log_ev_session.sh
# chmod +x /config/scripts/log_ev_session.sh
#
# Parametre: session_id start_time end_time user energy_kwh cost_eur
#            tariff stop_reason duration_min surplus_energy grid_energy surplus_value

# Debug log
echo "$(date): $@" >> /config/ev_session_debug.log

# CSV zapis - 12 stlpcov
echo "$1,$2,$3,$4,$5,$6,$7,$8,$9,${10},${11},${12}" >> /config/ev_charging_sessions.csv

# Kopiruj do www
mkdir -p /config/www
cp /config/ev_charging_sessions.csv /config/www/ev_charging_sessions.csv
cp /config/ev_charging_sessions.csv "/config/www/ev_sessions_$(date +%Y%m%d_%H%M%S).csv"
chmod 644 /config/www/*.csv