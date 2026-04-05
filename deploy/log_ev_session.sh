#!/bin/bash
# EV Session Logger - 12 stlpcov (s prebytkami)
# Parametre: session_id start_time end_time user energy_kwh cost_eur
#            tariff stop_reason duration_min surplus_energy grid_energy surplus_value

echo "$(date): $@" >> /config/ev_session_debug.log

echo "$1,$2,$3,$4,$5,$6,$7,$8,$9,${10},${11},${12}" >> /config/ev_charging_sessions.csv

mkdir -p /config/www
cp /config/ev_charging_sessions.csv /config/www/ev_charging_sessions.csv
chmod 644 /config/www/ev_charging_sessions.csv
