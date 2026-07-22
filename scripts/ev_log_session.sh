#!/bin/sh
# Zapíše ukončenú EV session do /config/ev_sessions.csv
# Volané z packages/ev_session.yaml -> shell_command.ev_log_session
#
# Dôvod existencie skriptu: HA shell_command pri použití {{ }} template-u NESPÚŠŤA
# príkaz cez shell, ale parsuje argumenty a spustí program priamo. Preto shell
# operátory (&&, ;, >, >>) v inline shell_command-e nefungujú — vyústili do
# `[: missing ]` / return code 2 a session sa nezapisovala. Logika preto patrí sem.
#
# Argumenty (20, v poradí stĺpcov CSV):
#   1 session_id  2 start  3 end  4 user  5 energy_kwh  6 charging_min
#   7 cost_eur  8 avg_price  9 solar_kwh  10 grid_kwh  11 solar_pct
#   12 t1_kwh  13 t2_kwh  14 t3_kwh  15 t4_kwh
#   16 soc_start  17 soc_end  18 odo_start  19 odo_end  20 stop_reason

CSV="/config/ev_sessions.csv"
HDR="session_id,start,end,user,energy_kwh,charging_min,cost_eur,avg_price,solar_kwh,grid_kwh,solar_pct,t1_kwh,t2_kwh,t3_kwh,t4_kwh,soc_start,soc_end,odo_start,odo_end,stop_reason"

[ -f "$CSV" ] || echo "$HDR" > "$CSV"

printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
  "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" \
  "${11}" "${12}" "${13}" "${14}" "${15}" "${16}" "${17}" "${18}" "${19}" "${20}" \
  >> "$CSV"

cp "$CSV" /config/www/ev_sessions.csv

# Obnov XLSX export (na pozadí, nech nezdržuje koniec session)
python3 /config/scripts/ev_export_xlsx.py >/dev/null 2>&1 &
