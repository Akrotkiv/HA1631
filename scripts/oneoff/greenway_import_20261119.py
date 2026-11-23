#!/usr/bin/env python3
"""Jednorazovo: nabíjania z GreenWay app (screenshoty 19.11.2026).
Dátumy existujúcich riadkov sa NEMENIA. Použitie: greenway_import_20261119.py <csv> [www]"""
import sys, subprocess
from datetime import datetime, timedelta
sys.path.insert(0, "/config/scripts")
import ev_ovms_perf as p

p.CSV = sys.argv[1]
if len(sys.argv) > 2:
    p.WWW = sys.argv[2]
AUP = "GreenWay Aupark Bratislava DC - parkovací dom"
UPDATE = [
    ("20261031_183923", 6.57, 2.56, AUP),   # GreenWay: 30.10. 16:46
    ("20261008_143835", 23.0, 8.97, AUP),
    ("20260909_124431", 22.66, 8.84, AUP),
]
NEW = [  # (start, min, kWh, €, typ, stanica)   15.02.2026 0,19 kWh/0 € = nepodarený štart → vynechané
    ("2026-05-02 17:03", 107, 21.21, 8.27, "DC", AUP),
    ("2026-03-25 12:11", 150, 17.21, 6.71, "AC", "GreenWay Avion #1 Bratislava"),
    ("2025-11-21 21:22", 39, 17.2, 10.15, "DC", "GreenWay Empark Trnava-Modranka"),
    ("2025-10-24 14:53", 74, 17.0, 10.03, "DC", "GreenWay OC Mlyny Nitra"),
    ("2025-04-12 22:50", 23, 11.34, 6.69, "DC", "GreenWay M Park Považská Bystrica"),
    ("2025-03-02 16:58", 136, 15.72, 6.13, "AC", "GreenWay Avion #1 Bratislava"),
]
h, b = p.read_csv()
ix = {c: i for i, c in enumerate(h)}
byid = {r[0]: r for r in b}
existing = [(p.ts(r[ix["start"]]), p.ts(r[ix["end"]])) for r in b
            if r[ix["user"]] == "mysan" and r[ix["start"]] and r[ix["end"]]]
upd = [(sid, k, c, n + (" · " + byid[sid][ix["comment"]] if byid[sid][ix["comment"]] and byid[sid][ix["comment"]].lower() not in n.lower() else ""))
       for sid, k, c, n in UPDATE]
ac_ids = []
for s, mins, kwh, cost, typ, note in NEW:
    st = datetime.strptime(s, "%Y-%m-%d %H:%M"); en = st + timedelta(minutes=mins)
    if any(x < en.timestamp() and y > st.timestamp() for x, y in existing):
        print("PREKRYV — preskakujem", s); continue
    d = {k: "" for k in h}
    d.update({"session_id": st.strftime("%Y%m%d_%H%M%S"), "start": st.strftime("%Y-%m-%d %H:%M:%S"),
              "end": en.strftime("%Y-%m-%d %H:%M:%S"), "user": "mysan", "energy_kwh": f"{kwh:.3f}",
              "charging_min": str(mins), "cost_eur": f"{cost:.2f}", "avg_price": f"{cost / kwh:.4f}",
              "solar_kwh": "0", "grid_kwh": f"{kwh:.3f}", "solar_pct": "0", "t1_kwh": "0", "t2_kwh": "0",
              "t3_kwh": "0", "t4_kwh": "0", "stop_reason": "dc_provider" if typ == "DC" else "manual_ext",
              "charge_type": typ, "provider": "GreenWay", "comment": note})
    b.append([d[k] for k in h])
    if typ == "DC":
        upd.append((d["session_id"], kwh, cost, note))
    else:
        ac_ids.append(d["session_id"])
b.sort(key=lambda r: r[ix["start"]])
print("AC perf:", p.apply(h, b, set(ac_ids)), ac_ids)
_pop = subprocess.Popen
subprocess.Popen = lambda *a, **k: None
p.write_csv(h, b)
for sid, kwh, cost, note in upd:
    print(sid, p.set_provider(sid, "GreenWay", kwh, cost, note))
subprocess.Popen = _pop
