#!/usr/bin/env python3
"""Migrate old ev_charging_sessions.csv → new ev_sessions.csv schema.

Old cols: session_id,start_time,end_time,user,energy_kwh,cost_eur,tariff,
          stop_reason,duration_min,surplus_energy_kwh,grid_energy_kwh,surplus_value_eur
New cols: session_id,start,end,user,energy_kwh,charging_min,cost_eur,avg_price,
          solar_kwh,grid_kwh,solar_pct,t1_kwh,t2_kwh,t3_kwh,t4_kwh,
          soc_start,soc_end,odo_start,odo_end,stop_reason

SOC/odometer have no historical data → left blank.
Tariff energy is binned into the single matching tX_kwh column (old data = 1 tariff/session).
"""
import csv

OLD = "/config/ev_charging_sessions.csv"
NEW = "/config/ev_sessions.csv"
HEADER = ["session_id", "start", "end", "user", "energy_kwh", "charging_min",
          "cost_eur", "avg_price", "solar_kwh", "grid_kwh", "solar_pct",
          "t1_kwh", "t2_kwh", "t3_kwh", "t4_kwh",
          "soc_start", "soc_end", "odo_start", "odo_end", "stop_reason"]


def f(v, d=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


def main():
    rows = []
    with open(OLD, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("session_id"):
                continue
            energy = f(r.get("energy_kwh"))
            cost = f(r.get("cost_eur"))
            surplus = f(r.get("surplus_energy_kwh"))
            grid = f(r.get("grid_energy_kwh"))
            tariff = (r.get("tariff") or "").strip().lower()  # t1..t4
            avg_price = round(cost / energy, 4) if energy > 0 else 0
            solar_pct = round(surplus / energy * 100, 0) if energy > 0 else 0
            tk = {"t1_kwh": 0, "t2_kwh": 0, "t3_kwh": 0, "t4_kwh": 0}
            if tariff in ("t1", "t2", "t3", "t4"):
                tk[tariff + "_kwh"] = round(energy, 3)
            rows.append([
                r.get("session_id", ""),
                r.get("start_time", ""),
                r.get("end_time", ""),
                r.get("user", ""),
                round(energy, 3),
                round(f(r.get("duration_min"))),
                round(cost, 3),
                avg_price,
                round(surplus, 3),
                round(grid, 3),
                solar_pct,
                tk["t1_kwh"], tk["t2_kwh"], tk["t3_kwh"], tk["t4_kwh"],
                "", "", "", "",                       # soc/odo: no historical data
                r.get("stop_reason", ""),
            ])

    with open(NEW, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"Migrated {len(rows)} sessions → {NEW}")


if __name__ == "__main__":
    main()
