#!/bin/bash
# EV Session Logger - 9 stlpcov
# chmod +x /config/scripts/log_ev_session.sh

# Debug log
echo "$(date): $@" >> /config/ev_session_debug.log

# CSV zapis - 9 stlpcov
echo "$1,$2,$3,$4,$5,$6,$7,$8,$9" >> /config/ev_charging_sessions.csv

# Kopiruj do www
mkdir -p /config/www
cp /config/ev_charging_sessions.csv /config/www/ev_charging_sessions.csv
cp /config/ev_charging_sessions.csv "/config/www/ev_sessions_$(date +%Y%m%d_%H%M%S).csv"
chmod 644 /config/www/*.csv
