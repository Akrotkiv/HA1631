#!/usr/bin/env python3
"""Jednorazovo: 1) vráti pôvodné dátumy 5 riadkov zmenených importom 18.11.,
2) doplní DC z druhého Lidl Plus konta (screenshoty 19.11.2026).
Použitie: lidl_import2_20261119.py <csv_path> [www_path]"""
import sys, csv, subprocess
sys.path.insert(0, "/config/scripts")
import ev_ovms_perf as p

p.CSV = sys.argv[1]
if len(sys.argv) > 2:
    p.WWW = sys.argv[2]
BAK = "/config/ev_sessions.csv.bak_20261118_lidl"

RESTORE = ["20261012_173337", "20261031_183923", "20261031_182042",
           "20261031_183951", "20261031_215626"]
UPDATE = [  # existujúce riadky ← Lidl (konto 2)
    ("20261031_183951", 12.69, 4.95, "Lidl Bernolákovo"),
    ("20260809_174425", 15.07, 5.88, "Lidl Bernolákovo"),
    ("20260728_201853", 13.45, 5.25, "Lidl Martin, Aurela Stodolu"),
    ("20260728_111009", 18.30, 7.14, "Lidl Martin, Aurela Stodolu"),
]
NEW = [  # (start, minúty, kWh, €, miesto)
    ("2026-09-13 18:25", 48, 17.54, 6.84, "Lidl Bernolákovo"),
    ("2026-07-16 14:00", 60, 21.87, 8.53, "Lidl Bernolákovo"),
    ("2026-06-19 13:04", 92, 25.55, 9.96, "Lidl Bernolákovo"),
    ("2026-04-28 12:55", 50, 17.16, 6.69, "Lidl Bernolákovo"),
    ("2026-03-25 19:02", 11, 7.98, 3.12, "Lidl Piešťany"),
    ("2026-03-17 14:15", 91, 26.97, 10.52, "Lidl Bernolákovo"),
    ("2026-03-02 16:08", 77, 17.14, 6.69, "Lidl Bernolákovo"),
    ("2026-02-28 16:11", 64, 19.43, 7.58, "Lidl Bernolákovo"),
    ("2025-12-19 14:09", 90, 29.17, 11.38, "Lidl Bernolákovo"),
    ("2025-11-17 08:58", 16, 10.79, 4.20, "Lidl Bernolákovo"),
    ("2025-10-25 13:19", 30, 4.63, 1.81, "Lidl Bernolákovo"),
    ("2025-09-21 17:38", 40, 6.09, 2.37, "Lidl Bernolákovo"),
    ("2025-09-21 16:38", 49, 20.69, 8.07, "Lidl Bernolákovo"),
]
from datetime import datetime, timedelta

h, b = p.read_csv()
ix = {c: i for i, c in enumerate(h)}
byid = {r[0]: r for r in b}
orig = {r[0]: r for r in csv.reader(open(BAK, newline=""))}
for sid in RESTORE:
    r, o = byid[sid], orig[sid]
    r[ix["start"]], r[ix["end"]] = o[ix["start"]], o[ix["end"]]
existing = [(p.ts(r[ix["start"]]), p.ts(r[ix["end"]])) for r in b
            if r[ix["user"]] == "mysan" and r[ix["start"]] and r[ix["end"]]]
for s, mins, kwh, cost, note in NEW:
    st = datetime.strptime(s, "%Y-%m-%d %H:%M")
    en = st + timedelta(minutes=mins)
    a, z = st.timestamp(), en.timestamp()
    if any(x < z and y > a for x, y in existing):
        print("PREKRYV — preskakujem", s); continue
    d = {k: "" for k in h}
    d.update({"session_id": st.strftime("%Y%m%d_%H%M%S"),
              "start": st.strftime("%Y-%m-%d %H:%M:%S"), "end": en.strftime("%Y-%m-%d %H:%M:%S"),
              "user": "mysan", "energy_kwh": f"{kwh:.3f}", "charging_min": str(mins),
              "cost_eur": "0", "avg_price": "0", "solar_kwh": "0", "grid_kwh": f"{kwh:.3f}",
              "solar_pct": "0", "t1_kwh": "0", "t2_kwh": "0", "t3_kwh": "0", "t4_kwh": "0",
              "stop_reason": "dc_provider", "charge_type": "DC", "provider": "Lidl"})
    b.append([d[k] for k in h])
    UPDATE.append((d["session_id"], kwh, cost, note))
b.sort(key=lambda r: r[ix["start"]])
_pop = subprocess.Popen
subprocess.Popen = lambda *a, **k: None
p.write_csv(h, b)
for sid, kwh, cost, note in UPDATE:
    print(p.set_provider(sid, "Lidl", kwh, cost, note))
subprocess.Popen = _pop
