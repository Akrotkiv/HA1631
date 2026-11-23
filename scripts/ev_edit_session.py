#!/usr/bin/env python3
"""Add / replace / delete rows in /config/ev_sessions.csv (manuálne session).

Volané z shell_command v packages/ev_manual_entry.yaml. Robota s CSV je v Pythone
(nie shell/printf), lebo csv.writer korektne rieši úvodzovky/čiarky a rewrite riadku
podľa session_id sa v shelli robí zle.

Riadok sa NEposiela ako 20 samostatných argumentov (HA shell_command by prázdne
argumenty mohol zlúčiť a rozhodiť stĺpce), ale ako JEDEN argument = CSV riadok
poskladaný v Jinja cez `join(',')`. Hodnoty nikdy neobsahujú čiarku (dátumy majú
medzeru, nie čiarku; desatinné číslo je '.'), takže split(',') je bezpečný — okrem posledného poľa
(comment), ktoré čiarku môže mať; preto sa riadok delí s maxsplit.

Použitie:
  ev_edit_session.py add     "<row_csv>"              # pridá nový riadok
  ev_edit_session.py replace "<old_id>" "<row_csv>"   # zmaže old_id, pridá nový
  ev_edit_session.py delete  "<session_id>"           # zmaže riadok

Po každej zmene: prepíše CSV, zrkadlí do /config/www/, pregeneruje XLSX (na pozadí).
"""
import csv
import os
import subprocess
import sys

CSV = "/config/ev_sessions.csv"
WWW = "/config/www/ev_sessions.csv"
# Riadok z UI má 23 polí (končí comment, ktorý môže obsahovať čiarky).
# Za ním nasleduje 8 OVMS performance stĺpcov — tie UI neposiela: pri replace sa
# zachovajú z pôvodného riadku a po add/replace sa prepočítajú (ev_ovms_perf.py fill).
NCOLS = 23
PERF_COLS = 8
TOTAL = NCOLS + PERF_COLS
HDR = ("session_id,start,end,user,energy_kwh,charging_min,cost_eur,avg_price,"
       "solar_kwh,grid_kwh,solar_pct,t1_kwh,t2_kwh,t3_kwh,t4_kwh,soc_start,"
       "soc_end,odo_start,odo_end,stop_reason,charge_type,provider,comment,"
       "battery_kwh,efficiency_pct,power_avg_kw,power_max_kw,car_eff_pct,"
       "bat_temp_start,bat_temp_end,soh")
OVMS_USER = "mysan"


def read_rows():
    if not os.path.exists(CSV):
        return [HDR.split(",")], []
    with open(CSV, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.reader(fh) if r]
    if not rows:
        return [HDR.split(",")], []
    header, body = rows[0], rows[1:]
    # migrácia schémy: doplň chýbajúce stĺpce (comment + OVMS perf)
    full = HDR.split(",")
    if len(header) < TOTAL:
        header = header + full[len(header):TOTAL]
    body = [r + [""] * (TOTAL - len(r)) if len(r) < TOTAL else r for r in body]
    return header, body


def is_dc_dup(new_row, r):
    """Automaticky zaznamenaná DC session (auto_dc), ktorú pokrýva ručne zadaný riadok."""
    from datetime import datetime
    if r[3] != new_row[3] or r[19] != "auto_dc":
        return False
    try:
        f = lambda s: datetime.strptime(s[:16], "%Y-%m-%d %H:%M").timestamp()
        a, b, ra, rb = f(new_row[1]), f(new_row[2]), f(r[1]), f(r[2])
    except (ValueError, IndexError):
        return False
    return ra < b + 900 and rb > a - 900


def fill_perf(row):
    if row[3] == OVMS_USER:
        try:
            subprocess.Popen(
                ["python3", "/config/scripts/ev_ovms_perf.py", "fill", row[0], "2"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


def write_rows(header, body):
    with open(CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(body)
    try:
        import shutil
        shutil.copy(CSV, WWW)
    except Exception:
        pass
    # XLSX na pozadí — nech nezdržuje HA službu
    try:
        subprocess.Popen(
            ["python3", "/config/scripts/ev_export_xlsx.py"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def parse_row(row_csv):
    """CSV riadok (jeden string) -> presne NCOLS polí (doplní / oreže).

    Posledné pole (comment) môže obsahovať čiarky — preto split s maxsplit.
    """
    fields = row_csv.split(",", NCOLS - 1)
    if len(fields) < NCOLS:
        fields += [""] * (NCOLS - len(fields))
    return fields[:NCOLS]


def main():
    if len(sys.argv) < 3:
        print("usage: add <row> | replace <old_id> <row> | delete <id>")
        return 1

    cmd = sys.argv[1]
    header, body = read_rows()

    if cmd == "add":
        new_row = parse_row(sys.argv[2]) + [""] * PERF_COLS
        # ručne zadaná DC session nahradí automatický auto_dc záznam z OVMS
        dups = [r for r in body if is_dc_dup(new_row, r)]
        body = [r for r in body if r not in dups]
        body.append(new_row)
        write_rows(header, body)
        fill_perf(new_row)
        print(f"added (replaced {len(dups)} auto_dc)" if dups else "added")

    elif cmd == "replace":
        old_id = sys.argv[2]
        new_row = parse_row(sys.argv[3]) if len(sys.argv) > 3 else None
        if new_row is None:
            print("replace: missing row")
            return 1
        old = next((r for r in body if r[0] == old_id), None)
        new_row = new_row + (old[NCOLS:TOTAL] if old else [""] * PERF_COLS)
        kept = [r for r in body if r[0] != old_id]
        removed = len(body) - len(kept)
        kept.append(new_row)
        write_rows(header, kept)
        fill_perf(new_row)
        print(f"replaced {old_id} ({removed} old row(s) removed)")

    elif cmd == "delete":
        sid = sys.argv[2]
        kept = [r for r in body if r[0] != sid]
        removed = len(body) - len(kept)
        write_rows(header, kept)
        print(f"deleted {sid} ({removed} row(s))")

    else:
        print(f"unknown cmd: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
