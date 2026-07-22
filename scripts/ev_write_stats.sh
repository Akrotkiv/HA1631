#!/bin/sh
# Zapíše výber pre sessions dashboard: obdobie, posun, metrika, filter auta
# $1=period $2=offset $3=metric $4=vehicle
printf '{"period":"%s","offset":%s,"metric":"%s","vehicle":"%s"}' \
  "$1" "$2" "${3:-Solar}" "${4:-Všetky}" > /config/.ev_stats.json
