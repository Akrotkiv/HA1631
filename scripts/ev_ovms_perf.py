#!/usr/bin/env python3
"""Doplní výkonové (performance) údaje z OVMS do /config/ev_sessions.csv.

Zdroj = HA recorder DB (/config/home-assistant_v2.db, read-only):
  - presná história `states` (~10 dní retencia)  → presné hodnoty
  - hodinové `statistics` (dlhodobo)              → aproximácia pre staršie session

Stĺpce (pridané za `comment`):
  battery_kwh     kWh, ktoré reálne prišli do batérie (OVMS v.c.kwh, finálna hodnota)
  efficiency_pct  battery_kwh / energy_kwh (wallbox AC meter) × 100  → straty AC→batéria
  power_avg_kw    battery_kwh / (charging_min / 60)  (priemer počas nabíjania, bez páuz)
  power_max_kw    max OVMS v.c.power počas session
  car_eff_pct     priemer OVMS v.c.efficiency (účinnosť nabíjačky v aute, hlási auto)
  bat_temp_start  teplota batérie na začiatku (°C)
  bat_temp_end    teplota batérie na konci (°C)
  soh             stav batérie (SOH %) na konci

Údaje sa počítajú len pre auto s OVMS (user == mysan).

Použitie:
  ev_ovms_perf.py fill <session_id> [delay_s]   # po konci session (volá ev_log_session.sh)
  ev_ovms_perf.py backfill [--force]            # doplní všetky mysan riadky s prázdnymi údajmi
"""
import csv
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

CSV = "/config/ev_sessions.csv"
WWW = "/config/www/ev_sessions.csv"
DB = "/config/home-assistant_v2.db"
OVMS_USER = "mysan"

BASE_HDR = ["session_id", "start", "end", "user", "energy_kwh", "charging_min",
            "cost_eur", "avg_price", "solar_kwh", "grid_kwh", "solar_pct",
            "t1_kwh", "t2_kwh", "t3_kwh", "t4_kwh", "soc_start", "soc_end",
            "odo_start", "odo_end", "stop_reason", "charge_type", "provider", "comment"]
PERF_HDR = ["battery_kwh", "efficiency_pct", "power_avg_kw", "power_max_kw",
            "car_eff_pct", "bat_temp_start", "bat_temp_end", "soh"]
HDR = BASE_HDR + PERF_HDR

E_KWH = "sensor.mysan_charge_energy"
E_PWR = "sensor.mysan_charge_power"
E_EFF = "sensor.mysan_charging_efficiency"
E_TMP = "sensor.mysan_battery_temperature"
E_SOH = "sensor.mysan_battery_health"

# Sanity: účinnosť AC→batéria mimo tohto rozsahu = chybné dáta (stale v.c.kwh, reset…)
EFF_MIN, EFF_MAX = 60.0, 100.0


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ts(s):
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").timestamp()


# ---------------------------------------------------------------- DB helpers
class Src:
    def __init__(self):
        self.c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)

    def states(self, eid, a, b):
        """[(ts, float)] v okne [a, b], len číselné stavy."""
        q = """select s.last_updated_ts, s.state from states s
               join states_meta m on s.metadata_id = m.metadata_id
               where m.entity_id = ? and s.last_updated_ts between ? and ?
               order by s.last_updated_ts"""
        return [(t, f) for t, v in self.c.execute(q, (eid, a, b))
                if (f := fnum(v)) is not None]

    def state_at(self, eid, t, max_age=6 * 3600):
        """Posledná číselná hodnota <= t (nie staršia než max_age)."""
        q = """select s.state from states s
               join states_meta m on s.metadata_id = m.metadata_id
               where m.entity_id = ? and s.last_updated_ts between ? and ?
               order by s.last_updated_ts desc"""
        for (v,) in self.c.execute(q, (eid, t - max_age, t)):
            f = fnum(v)
            if f is not None:
                return f
        return None

    def states_cover(self, eid, t):
        """Má states históriu pre čas t? (retencia recordera)"""
        q = """select min(s.last_updated_ts) from states s
               join states_meta m on s.metadata_id = m.metadata_id where m.entity_id = ?"""
        r = self.c.execute(q, (eid,)).fetchone()
        return r and r[0] is not None and r[0] <= t

    def stats(self, eid, a, b):
        """Hodinové štatistiky [(start_ts, mean, min, max)] pre hodiny prekrývajúce [a, b]."""
        q = """select s.start_ts, s.mean, s.min, s.max from statistics s
               join statistics_meta m on s.metadata_id = m.id
               where m.statistic_id = ? and s.start_ts > ? and s.start_ts <= ?
               order by s.start_ts"""
        return list(self.c.execute(q, (eid, a - 3600, b)))

    def sum_delta(self, eid, a, b):
        """Prírastok počítadla (statistics.sum) od začiatku hodiny so štartom po koniec hodiny s koncom."""
        q = """select s.sum from statistics s join statistics_meta m on s.metadata_id = m.id
               where m.statistic_id = ? and s.start_ts <= ? and s.sum is not null
               order by s.start_ts desc limit 1"""
        h0 = (a // 3600) * 3600 - 3600   # hodina pred štartom (jej sum = stav na začiatku)
        h1 = (b // 3600) * 3600          # hodina s koncom
        s0 = self.c.execute(q, (eid, h0)).fetchone()
        s1 = self.c.execute(q, (eid, h1)).fetchone()
        if not s0 or not s1 or s1[0] is None or s0[0] is None:
            return None
        d = s1[0] - s0[0]
        return d if d > 0 else None


# ---------------------------------------------------------------- compute
def compute(src, row):
    """Vráti dict PERF_HDR → hodnota (str) alebo None ak nie sú dáta."""
    try:
        a, b = ts(row["start"]), ts(row["end"])
    except (KeyError, ValueError):
        return None
    energy = fnum(row.get("energy_kwh")) or 0.0
    cmin = fnum(row.get("charging_min")) or 0.0
    out = {k: "" for k in PERF_HDR}

    if src.states_cover(E_KWH, a):
        # --- presne zo states
        kwh = src.states(E_KWH, a - 60, b + 120)
        # v.c.kwh sa resetuje pri štarte nabíjania; finálna hodnota = posledná > 0
        batt = next((v for _, v in reversed(kwh) if v > 0), None)
        pwr = [v for _, v in src.states(E_PWR, a - 60, b + 120) if v > 0]
        pmax = max(pwr) if pwr else None
        # účinnosť auta len počas reálneho nabíjania (po konci OVMS hlási 100)
        ptimes = [t for t, v in src.states(E_PWR, a - 60, b + 120) if v > 0]
        if ptimes:
            eff = [v for t, v in src.states(E_EFF, ptimes[0], ptimes[-1]) if 0 < v < 100]
        else:
            eff = []
        car_eff = sum(eff) / len(eff) if eff else None
        t_start = src.state_at(E_TMP, a + 300)
        t_end = src.state_at(E_TMP, b + 120)
        soh = src.state_at(E_SOH, b + 120, max_age=7 * 86400)
        if soh is None:  # SOH sa mení zriedka → v states často nie je, vezmi štatistiku
            sst = src.stats(E_SOH, a, b)
            soh = sst[-1][3] if sst else None
    else:
        # --- aproximácia z hodinových štatistík
        # v.c.kwh má štatistiku ako počítadlo (sum) → prírastok za hodiny session
        batt = src.sum_delta(E_KWH, a, b)
        pst = src.stats(E_PWR, a, b)
        pmax = max((r[3] for r in pst if r[3]), default=None)
        # účinnosť auta: priemer hodín, kde sa celú hodinu nabíjalo (min výkonu > 0)
        charging_h = {r[0] for r in pst if r[2] and r[2] > 0}
        eff = [r[1] for r in src.stats(E_EFF, a, b) if r[0] in charging_h and r[1]]
        car_eff = sum(eff) / len(eff) if eff else None
        tst = src.stats(E_TMP, a, b)
        t_start = tst[0][1] if tst else None
        t_end = tst[-1][1] if tst else None
        sst = src.stats(E_SOH, a, b)
        soh = sst[-1][3] if sst else None

    is_dc = (row.get("charge_type") or "").upper() == "DC"
    # DC doplnené od providera: kWh do batérie už poznáme presne (OVMS e-mail / auto záznam,
    # uložené v set_provider) → má prednosť pred DB (hodinové štatistiky sú len odhad)
    if is_dc and row.get("stop_reason") == "dc_provider" and fnum(row.get("battery_kwh")):
        batt = fnum(row.get("battery_kwh"))
    if batt is not None and energy > 0:
        eff_pct = batt / energy * 100
        # DC: energy_kwh je zvyčajne tiež z OVMS (e-mail / auto) → pomer nemá zmysel.
        # Výnimka: dc_provider = kWh z účtu providera → účinnosť nabíjačka→batéria má zmysel.
        from_provider = is_dc and row.get("stop_reason") == "dc_provider"
        ok = (EFF_MIN <= eff_pct <= EFF_MAX + 5) if from_provider else \
             (eff_pct <= 105) if is_dc else (EFF_MIN <= eff_pct <= EFF_MAX)
        if ok:
            out["battery_kwh"] = f"{batt:.3f}"
            if not is_dc or from_provider:
                out["efficiency_pct"] = f"{eff_pct:.1f}"
            if cmin > 0:
                out["power_avg_kw"] = f"{batt / (cmin / 60):.2f}"
    if pmax is not None:
        out["power_max_kw"] = f"{pmax:.1f}"
    if car_eff is not None and not is_dc:  # pri DC sa nabíjačka v aute nepoužíva
        out["car_eff_pct"] = f"{car_eff:.1f}"
    if t_start is not None:
        out["bat_temp_start"] = f"{t_start:.0f}"
    if t_end is not None:
        out["bat_temp_end"] = f"{t_end:.0f}"
    if soh is not None:
        out["soh"] = f"{soh:.0f}"
    return out if any(out.values()) else None


# ---------------------------------------------------------------- CSV io
def read_csv():
    with open(CSV, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.reader(fh) if r]
    header, body = rows[0], rows[1:]
    # migrácia schémy: doplň chýbajúce stĺpce (comment + perf)
    for col in HDR:
        if col not in header:
            header.append(col)
    n = len(header)
    body = [r + [""] * (n - len(r)) for r in body]
    return header, body


def write_csv(header, body):
    tmp = CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(body)
    os.replace(tmp, CSV)
    try:
        shutil.copy(CSV, WWW)
    except Exception:
        pass
    subprocess.Popen(["python3", "/config/scripts/ev_export_xlsx.py"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply(header, body, ids=None, force=False):
    src = Src()
    idx = {c: i for i, c in enumerate(header)}
    done = 0
    for r in body:
        d = dict(zip(header, r))
        if d.get("user") != OVMS_USER:
            continue
        if ids is not None and d.get("session_id") not in ids:
            continue
        if not force and any(d.get(k) for k in PERF_HDR):
            continue
        perf = compute(src, d)
        if not perf:
            continue
        for k, v in perf.items():
            r[idx[k]] = v
        done += 1
    return done


def add_dc(start, end):
    """Pridá automaticky zaznamenanú DC session (stop_reason=auto_dc).

    energy_kwh = OVMS v.c.kwh (do batérie). Cena/poskytovateľ nie sú známe →
    cost 0, provider '?' — doplní sa cez Upraviť. Ak už existuje mysan riadok,
    ktorý sa časovo prekrýva (napr. ručne zadaný z e-mailu), nič sa nepridá.
    """
    a, b = ts(start), ts(end)
    src = Src()
    kwh = src.states(E_KWH, a - 60, b + 120)
    energy = next((v for _, v in reversed(kwh) if v > 0), None)
    if not energy:
        return "dc: no energy in OVMS data"
    header, body = read_csv()
    for r in body:
        d = dict(zip(header, r))
        if d.get("user") != OVMS_USER:
            continue
        try:
            ra, rb = ts(d["start"]), ts(d["end"])
        except (KeyError, ValueError):
            continue
        if ra < b + 600 and rb > a - 600:
            return f"dc: overlaps existing {d.get('session_id')} — skipped"
    soc_s = src.state_at("sensor.mysan_battery_level", a)
    soc_e = src.state_at("sensor.mysan_battery_level", b + 120)
    odo = src.state_at("sensor.mysan_odometer", b + 120, max_age=30 * 86400)
    cmin = max(round((b - a) / 60), 1)
    sid = datetime.fromtimestamp(a).strftime("%Y%m%d_%H%M%S")
    d = {k: "" for k in header}
    d.update({
        "session_id": sid, "start": start[:19], "end": end[:19], "user": OVMS_USER,
        "energy_kwh": f"{energy:.3f}", "charging_min": str(cmin),
        "cost_eur": "0", "avg_price": "0", "solar_kwh": "0", "grid_kwh": f"{energy:.3f}",
        "solar_pct": "0", "t1_kwh": "0", "t2_kwh": "0", "t3_kwh": "0", "t4_kwh": "0",
        "soc_start": f"{soc_s:.0f}" if soc_s is not None else "",
        "soc_end": f"{soc_e:.0f}" if soc_e is not None else "",
        "odo_end": f"{odo:.0f}" if odo is not None else "",
        "stop_reason": "auto_dc", "charge_type": "DC", "provider": "?",
        "comment": "auto OVMS — doplň cenu a poskytovateľa",
    })
    d.update(compute(src, d) or {})
    body.append([d.get(k, "") for k in header])
    write_csv(header, body)
    return f"dc: added {sid} {energy:.2f} kWh"


def set_provider(sid, prov, kwh, cost, note=""):
    """DC session ← údaje od providera. energy_kwh = kWh z účtu (fakturované),
    battery_kwh ostáva z OVMS → efficiency_pct = straty nabíjačka→batéria."""
    if kwh <= 0:
        return "provider: kWh musí byť > 0"
    header, body = read_csv()
    idx = {c: i for i, c in enumerate(header)}
    row = next((r for r in body if r[0] == sid), None)
    if row is None:
        return f"provider: session {sid} neexistuje"
    # pôvodná energia DC riadku = OVMS kWh do batérie (e-mail / auto_dc) → zachovaj ako battery_kwh
    prev = fnum(row[idx["energy_kwh"]])
    if row[idx["charge_type"]] == "DC" and row[idx["stop_reason"]] in ("manual_ext", "auto_dc") and prev:
        row[idx["battery_kwh"]] = f"{prev:.3f}"
    note = note.replace("\n", " ").replace("\r", " ").strip()
    if note.lower() in ("unknown", "unavailable"):
        note = ""
    upd = {
        "energy_kwh": f"{kwh:.3f}", "grid_kwh": f"{kwh:.3f}", "solar_kwh": "0", "solar_pct": "0",
        "cost_eur": f"{cost:.2f}", "avg_price": f"{cost / kwh:.4f}",
        "provider": prov, "charge_type": "DC", "stop_reason": "dc_provider",
        "comment": note if note else ("" if row[idx["comment"]].startswith("auto OVMS") else row[idx["comment"]]),
    }
    for k, v in upd.items():
        row[idx[k]] = v
    perf = compute(Src(), dict(zip(header, row)))
    for k, v in (perf or {}).items():
        row[idx[k]] = v
    if perf and not perf.get("battery_kwh"):  # nezmyselný pomer → nenechávaj starú hodnotu
        row[idx["battery_kwh"]] = ""
    write_csv(header, body)
    d = dict(zip(header, row))
    eff = f", účinnosť {d['efficiency_pct']} %" if d.get("efficiency_pct") else ""
    return f"{prov}: {kwh:.2f} kWh za {cost:.2f} € ({cost / kwh:.3f} €/kWh){eff}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "fill":
        sid = sys.argv[2]
        delay = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        time.sleep(delay)  # nech OVMS stihne poslať finálne metriky a recorder ich zapíše
        header, body = read_csv()
        n = apply(header, body, ids={sid}, force=True)
        if n:
            write_csv(header, body)
        print(f"fill {sid}: {n}")
    elif cmd == "dc":
        # DC (CHAdeMO / OVMS charge mode "performance") — celý riadok z OVMS dát
        start, end = sys.argv[2], sys.argv[3]
        delay = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        time.sleep(delay)
        print(add_dc(start, end))
    elif cmd == "provider":
        # doplnenie DC session údajmi z účtu providera: kWh + cena
        sid, prov, kwh, cost = sys.argv[2], sys.argv[3], fnum(sys.argv[4]), fnum(sys.argv[5])
        note = sys.argv[6] if len(sys.argv) > 6 else ""
        print(set_provider(sid, prov, kwh or 0.0, cost or 0.0, note))
    elif cmd == "backfill":
        header, body = read_csv()
        n = apply(header, body, force="--force" in sys.argv)
        write_csv(header, body)
        print(f"backfill: {n} rows")
    else:
        print(f"unknown cmd: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
