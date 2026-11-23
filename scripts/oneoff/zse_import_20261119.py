#!/usr/bin/env python3
"""Jednorazovo: DC (a 1 AC) nabíjania zo ZSE Drive app (screenshoty 19.11.2026).
Dátumy existujúcich riadkov sa NEMENIA. Použitie: zse_import_20261119.py <csv> [www]"""
import sys, subprocess
from datetime import datetime, timedelta
sys.path.insert(0, "/config/scripts")
import ev_ovms_perf as p

p.CSV = sys.argv[1]
if len(sys.argv) > 2:
    p.WWW = sys.argv[2]

UPDATE = [  # (sid, kWh, €, stanica)
    ("20261031_215626", 4.15, 2.03, "ZSE PN OD Prior 2"),          # ZSE: 30.10.
    ("20260928_194237", 27.33, 13.39, "ZSE BA Hlavná stanica"),    # ZSE: 03.10.
    ("20260830_170451", 23.18, 11.36, "ZSE BA Hlavná stanica"),
    ("20260928_110243", 22.41, 10.98, "ZSE BA OC Galéria Cubicon 2"),
    ("20261104_144708", 24.96, 12.23, "ZSE BA OC Galéria Cubicon 2"),
]
NEW = [  # (start, min, kWh, €, stanica) — časy odhad z hodinových OVMS štatistík
    ("2026-10-22 14:00", 75, 22.02, 10.79, "ZSE BA OC Galéria Cubicon 2 (čas odhad z OVMS)"),
    ("2026-07-22 13:25", 70, 21.02, 10.30, "ZSE BA OC Galéria Cubicon 2 (čas odhad z OVMS)"),
]
AC_FIX = ("20260913_144849", 3.74, "ZSE BA Rezident Malokarpatské námestie AC CL 2")

h, b = p.read_csv()
ix = {c: i for i, c in enumerate(h)}
byid = {r[0]: r for r in b}
# AC riadok: len cena + stanica, typ AC ostáva
r = byid[AC_FIX[0]]
r[ix["cost_eur"]] = f"{AC_FIX[1]:.2f}"
r[ix["avg_price"]] = f"{AC_FIX[1] / float(r[ix['energy_kwh']]):.4f}"
r[ix["comment"]] = AC_FIX[2]
existing = [(p.ts(r[ix["start"]]), p.ts(r[ix["end"]])) for r in b
            if r[ix["user"]] == "mysan" and r[ix["start"]] and r[ix["end"]]]
upd = [(sid, k, c, n + (" · " + byid[sid][ix["comment"]] if byid[sid][ix["comment"]] else ""))
       for sid, k, c, n in UPDATE]
for s, mins, kwh, cost, note in NEW:
    st = datetime.strptime(s, "%Y-%m-%d %H:%M"); en = st + timedelta(minutes=mins)
    if any(x < en.timestamp() and y > st.timestamp() for x, y in existing):
        print("PREKRYV — preskakujem", s); continue
    d = {k: "" for k in h}
    d.update({"session_id": st.strftime("%Y%m%d_%H%M%S"), "start": st.strftime("%Y-%m-%d %H:%M:%S"),
              "end": en.strftime("%Y-%m-%d %H:%M:%S"), "user": "mysan", "energy_kwh": f"{kwh:.3f}",
              "charging_min": str(mins), "cost_eur": "0", "avg_price": "0", "solar_kwh": "0",
              "grid_kwh": f"{kwh:.3f}", "solar_pct": "0", "t1_kwh": "0", "t2_kwh": "0", "t3_kwh": "0",
              "t4_kwh": "0", "stop_reason": "dc_provider", "charge_type": "DC", "provider": "ZSE"})
    b.append([d[k] for k in h])
    upd.append((d["session_id"], kwh, cost, note))
b.sort(key=lambda r: r[ix["start"]])
_pop = subprocess.Popen
subprocess.Popen = lambda *a, **k: None
p.write_csv(h, b)
for sid, kwh, cost, note in upd:
    print(sid, p.set_provider(sid, "ZSE", kwh, cost, note))
subprocess.Popen = _pop
