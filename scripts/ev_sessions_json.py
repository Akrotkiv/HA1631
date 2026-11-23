#!/usr/bin/env python3
"""Aggregate /config/ev_sessions.csv for the EV stats dashboard (evcc-style).

Reads control file /config/.ev_stats.json = {"period": "Mesiac|Rok|Celkom", "offset": int}
(offset = periods back from now; 0 = current).

Emits single-line JSON consumed by command_line sensor `sensor.ev_sessions_table`:
  {
    "count": <rows in selected period>,
    "label": "Marec 2026" | "2026" | "Celkom",
    "head_kwh", "head_cost", "head_solar_pct",
    "chart_mode": "day" | "month",
    "chart": [{"t": epoch_ms, "solar": x, "grid": y}, ...],
    "sessions": [ ...rows of selected period, newest first, max 60... ],
    "all_count", "all_kwh", "all_cost"
  }
"""
import calendar
import csv
import json
import os
from datetime import datetime

CSV_PATH = "/config/ev_sessions.csv"
CTRL_PATH = "/config/.ev_stats.json"
MAX_ROWS = 60

SK_MONTHS = ["", "Január", "Február", "Marec", "Apríl", "Máj", "Jún",
             "Júl", "August", "September", "Október", "November", "December"]
NUM_FIELDS = {"energy_kwh", "charging_min", "cost_eur", "avg_price", "solar_kwh",
              "grid_kwh", "solar_pct", "t1_kwh", "t2_kwh", "t3_kwh", "t4_kwh",
              "soc_start", "soc_end", "odo_start", "odo_end"}
# OVMS performance (prázdne = bez dát → None, nie 0)
PERF_FIELDS = {"battery_kwh", "efficiency_pct", "power_avg_kw", "power_max_kw", "car_eff_pct", "bat_temp_start", "bat_temp_end", "soh"}


def num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 3)
    except (ValueError, TypeError):
        return 0


def epoch_ms(y, m, d):
    return int(datetime(y, m, d, 12, 0).timestamp() * 1000)


def read_ctrl():
    try:
        with open(CTRL_PATH) as fh:
            c = json.load(fh)
        return (c.get("period", "Mesiac"), int(c.get("offset", 0)),
                c.get("metric", "Solar"), c.get("vehicle", "Všetky"))
    except Exception:
        return "Mesiac", 0, "Solar", "Všetky"


def load_rows():
    rows = []
    if not os.path.exists(CSV_PATH):
        return rows
    with open(CSV_PATH, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("session_id"):
                continue
            for k in list(r.keys()):
                if k in NUM_FIELDS:
                    r[k] = num(r[k])
                elif k in PERF_FIELDS:
                    r[k] = num(r[k]) if (r[k] or "").strip() else None
            # AC/DC + poskytovateľ (staré riadky bez stĺpca → default Home/AC)
            ct = (r.get("charge_type") or "").strip().upper()
            r["charge_type"] = ct if ct in ("AC", "DC") else "AC"
            r["provider"] = (r.get("provider") or "").strip() or "Home"
            r["comment"] = (r.get("comment") or "").strip()
            start = r.get("start", "")
            r["date"] = start[5:10].replace("-", ".")   # MM.DD short
            r["time"] = start[11:16]
            try:
                d = datetime.strptime(start[:10], "%Y-%m-%d")
                r["_y"], r["_m"], r["_d"] = d.year, d.month, d.day
            except ValueError:
                r["_y"] = r["_m"] = r["_d"] = 0
            rows.append(r)
    return rows


def main():
    period, offset, metric, vehicle = read_ctrl()
    rows = load_rows()
    now = datetime.now()

    all_kwh = round(sum(float(r.get("energy_kwh", 0) or 0) for r in rows), 1)
    all_cost = round(sum(float(r.get("cost_eur", 0) or 0) for r in rows), 2)

    # determine target window + chart buckets  (bucket = [solar, grid, cost])
    def add(b, r):
        b[0] += float(r.get("solar_kwh", 0) or 0)
        b[1] += float(r.get("grid_kwh", 0) or 0)
        b[2] += float(r.get("cost_eur", 0) or 0)

    if period == "Mesiac":
        m = now.month - offset
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        sel = [r for r in rows if r["_y"] == y and r["_m"] == m]
        label = f"{SK_MONTHS[m]} {y}"
        # daily buckets — vyplň všetky dni mesiaca (do dnešného dňa pri aktuálnom)
        buckets = {}
        for r in sel:
            add(buckets.setdefault(r["_d"], [0.0, 0.0, 0.0]), r)
        last_day = now.day if (y == now.year and m == now.month) else calendar.monthrange(y, m)[1]
        chart = [{"x": d, "solar": round(buckets.get(d, [0, 0, 0])[0], 2),
                  "grid": round(buckets.get(d, [0, 0, 0])[1], 2),
                  "cost": round(buckets.get(d, [0, 0, 0])[2], 2)}
                 for d in range(1, last_day + 1)]
        chart_mode = "day"
    elif period == "Rok":
        y = now.year - offset
        sel = [r for r in rows if r["_y"] == y]
        label = str(y)
        buckets = {}
        for r in sel:
            add(buckets.setdefault(r["_m"], [0.0, 0.0, 0.0]), r)
        last_m = now.month if y == now.year else 12
        chart = [{"x": SK_MONTHS[mm][:3], "solar": round(buckets.get(mm, [0, 0, 0])[0], 2),
                  "grid": round(buckets.get(mm, [0, 0, 0])[1], 2),
                  "cost": round(buckets.get(mm, [0, 0, 0])[2], 2)}
                 for mm in range(1, last_m + 1)]
        chart_mode = "month"
    else:  # Celkom
        sel = rows
        label = "Celkom"
        buckets = {}
        for r in sel:
            add(buckets.setdefault((r["_y"], r["_m"]), [0.0, 0.0, 0.0]), r)
        chart = [{"x": f"{mm}/{str(yy)[2:]}", "solar": round(v[0], 2),
                  "grid": round(v[1], 2), "cost": round(v[2], 2)}
                 for (yy, mm), v in sorted(buckets.items())]
        chart_mode = "month"

    head_kwh = round(sum(float(r.get("energy_kwh", 0) or 0) for r in sel), 1)
    head_cost = round(sum(float(r.get("cost_eur", 0) or 0) for r in sel), 2)
    head_solar = round(sum(float(r.get("solar_kwh", 0) or 0) for r in sel), 1)
    head_solar_pct = round(head_solar / head_kwh * 100) if head_kwh > 0 else 0

    # by-vehicle breakdown (celé obdobie, nezávislé od filtra tabuľky)
    veh = {}
    for r in sel:
        u = (r.get("user") or "?").strip() or "?"
        b = veh.setdefault(u, [0.0, 0.0, 0.0])
        b[0] += float(r.get("energy_kwh", 0) or 0)
        b[1] += float(r.get("cost_eur", 0) or 0)
        b[2] += float(r.get("solar_kwh", 0) or 0)
    by_vehicle = [
        {"name": u, "energy": round(e, 1), "cost": round(c, 2),
         "solar_pct": round(s / e * 100) if e > 0 else 0}
        for u, (e, c, s) in sorted(veh.items(), key=lambda kv: -kv[1][0])
    ]

    # AC/DC breakdown (vybrané obdobie)
    mode = {}
    for r in sel:
        mk = r.get("charge_type") or "AC"
        b = mode.setdefault(mk, [0.0, 0.0, 0])
        b[0] += float(r.get("energy_kwh", 0) or 0)
        b[1] += float(r.get("cost_eur", 0) or 0)
        b[2] += 1
    by_mode = [
        {"name": k, "energy": round(e, 1), "cost": round(c, 2), "count": n}
        for k, (e, c, n) in sorted(mode.items())
    ]

    # by-provider breakdown (vybrané obdobie)
    prov = {}
    for r in sel:
        p = (r.get("provider") or "Home").strip() or "Home"
        b = prov.setdefault(p, [0.0, 0.0, 0.0])
        b[0] += float(r.get("energy_kwh", 0) or 0)
        b[1] += float(r.get("cost_eur", 0) or 0)
        b[2] += float(r.get("solar_kwh", 0) or 0)
    by_provider = [
        {"name": p, "energy": round(e, 1), "cost": round(c, 2),
         "solar_pct": round(s / e * 100) if e > 0 else 0}
        for p, (e, c, s) in sorted(prov.items(), key=lambda kv: -kv[1][0])
    ]

    # zoznam všetkých áut v dátach (pre dynamický filter tabuľky)
    vehicles = sorted({(r.get("user") or "").strip() for r in rows if (r.get("user") or "").strip()})
    # zoznam všetkých poskytovateľov v dátach (pre dynamický výber)
    providers = sorted({(r.get("provider") or "").strip() for r in rows if (r.get("provider") or "").strip()})

    # table: filter podľa auta, newest first, strip internal keys
    table_src = sel if vehicle in ("Všetky", "", None) else [r for r in sel if (r.get("user") or "") == vehicle]
    sel_sorted = sorted(table_src, key=lambda r: r.get("start", ""), reverse=True)[:MAX_ROWS]
    for r in sel_sorted:
        for k in ("_y", "_m", "_d"):
            r.pop(k, None)

    # DC čakajúce na údaje od providera (auto_dc z OVMS) — celá história, najnovšie prvé
    dc_pending = [
        {"id": r["session_id"],
         "label": f"{r['session_id']} | {r['start'][8:10]}.{r['start'][5:7]} {r['time']}"
                  f" · {r['energy_kwh']} kWh · {r.get('soc_start') or '?'}→{r.get('soc_end') or '?'} %",
         "kwh": r["energy_kwh"]}
        for r in sorted(rows, key=lambda r: r.get("start", ""), reverse=True)
        if r.get("stop_reason") == "auto_dc"
    ][:15]
    # posledná DC cena €/kWh u každého poskytovateľa (predvyplnenie ceny)
    provider_prices = {}
    for r in sorted(rows, key=lambda r: r.get("start", "")):
        if r.get("charge_type") == "DC" and r.get("stop_reason") != "auto_dc":
            p = (r.get("provider") or "").strip()
            if p and p not in ("?", "Home"):
                provider_prices[p] = r.get("avg_price") or 0

    out = {
        "count": len(sel),
        "dc_pending": dc_pending,
        "provider_prices": provider_prices,
        "label": label,
        "period": period,
        "offset": offset,
        "metric": metric,
        "vehicle": vehicle,
        "head_kwh": head_kwh,
        "head_cost": head_cost,
        "head_solar_pct": head_solar_pct,
        "chart_mode": chart_mode,
        "chart": chart,
        "by_vehicle": by_vehicle,
        "by_mode": by_mode,
        "by_provider": by_provider,
        "vehicles": vehicles,
        "providers": providers,
        "sessions": sel_sorted,
        "all_count": len(rows),
        "all_kwh": all_kwh,
        "all_cost": all_cost,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
