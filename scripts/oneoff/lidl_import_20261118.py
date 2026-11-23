#!/usr/bin/env python3
"""Jednorazový import DC nabíjaní z Lidl Plus app (screenshoty 18.11.2026).
Použitie: lidl_import_20261118.py <csv_path>"""
import sys
sys.path.insert(0, "/config/scripts")
import ev_ovms_perf as p

p.CSV = sys.argv[1]
if len(sys.argv) > 2:
    p.WWW = sys.argv[2]

# 1) oprava dátumov (overené OVMS históriou: v pôvodný deň žiadne DC)
DATE_FIX = {
    "20261012_173337": "2026-10-11",
    "20261031_183923": "2026-10-30", "20261031_182042": "2026-10-30",
    "20261031_183951": "2026-10-30", "20261031_215626": "2026-10-30",
}
# 2) existujúce riadky ← Lidl kWh / € / miesto
UPDATE = [
    ("20260807_154957", 15.29, 5.96, "Lidl Bernolákovo"),
    ("20260909_203921", 7.13, 2.78, "Lidl Piešťany"),
    ("20261004_143204", 3.54, 1.38, "Lidl Bernolákovo"),
    ("20261004_173904", 1.47, 0.57, "Lidl Bernolákovo"),
    ("20261008_180007", 3.78, 1.48, "Lidl Nové Mesto nad Váhom, Malinovského"),
    ("20261011_151916", 7.35, 2.87, "Lidl Bernolákovo"),
    ("20261012_173337", 19.55, 7.63, "Lidl Bernolákovo"),
    ("20261027_180749", 9.44, 3.68, "Lidl Trnava, Hospodárska"),
    ("20261031_182042", 6.27, 2.44, "Lidl Bernolákovo - chybné odpojenie"),
    ("20261117_152403", 9.44, 3.68, "Lidl Trenčín, Bratislavská"),
]
# 3) chýbajúce session: (start, end, kWh, €, miesto)
NEW = [
    ("2026-06-30 08:55:00", "2026-06-30 09:20:00", 14.74, 5.75, "Lidl Nitra, Dolnočermánska (čas odhad z OVMS)"),
    ("2026-10-22 12:21:00", "2026-10-22 12:29:00", 4.64, 1.81, "Lidl Bernolákovo"),
    ("2026-10-22 16:27:00", "2026-10-22 16:47:00", 4.18, 1.63, "Lidl Bernolákovo"),
    ("2026-11-04 18:04:00", "2026-11-04 18:12:00", 3.61, 1.40, "Lidl Piešťany, Bratislavská 114"),
]
# 17.11: presné časy z Lidl (OVMS zachytil až prvú správu o 15:24)
TIMES = {"20261117_152403": ("2026-11-17 15:21:00", "2026-11-17 15:40:00", 18)}

h, b = p.read_csv()
ix = {c: i for i, c in enumerate(h)}
byid = {r[0]: r for r in b}
for sid, d in DATE_FIX.items():
    r = byid[sid]
    r[ix["start"]] = d + r[ix["start"]][10:]
    end = r[ix["end"]]
    # koniec v rovnaký deň ako pôvodne → posuň o rovnaký počet dní (všetky -1 deň)
    r[ix["end"]] = d + end[10:]
for sid, (s, e, m) in TIMES.items():
    r = byid[sid]
    r[ix["start"]], r[ix["end"]], r[ix["charging_min"]] = s, e, str(m)
existing = {r[ix["start"]][:16] for r in b if r[ix["user"]] == "mysan"}
for s, e, kwh, cost, note in NEW:
    if s[:16] in existing:
        print("skip existing", s); continue
    d = {k: "" for k in h}
    d.update({"session_id": s[:10].replace("-", "") + "_" + s[11:19].replace(":", ""),
              "start": s, "end": e, "user": "mysan", "energy_kwh": f"{kwh:.3f}",
              "charging_min": str(round((p.ts(e) - p.ts(s)) / 60)), "cost_eur": "0", "avg_price": "0",
              "solar_kwh": "0", "grid_kwh": f"{kwh:.3f}", "solar_pct": "0",
              "t1_kwh": "0", "t2_kwh": "0", "t3_kwh": "0", "t4_kwh": "0",
              "stop_reason": "dc_provider", "charge_type": "DC", "provider": "Lidl"})  # kWh už je od providera
    b.append([d[k] for k in h])
    UPDATE.append((d["session_id"], kwh, cost, note))
b.sort(key=lambda r: r[ix["start"]])
import subprocess
_pop = subprocess.Popen
subprocess.Popen = lambda *a, **k: None   # xlsx export až na konci
p.write_csv(h, b)
for sid, kwh, cost, note in UPDATE:
    print(p.set_provider(sid, "Lidl", kwh, cost, note))
subprocess.Popen = _pop
