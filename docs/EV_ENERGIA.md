# EV & Energia — manuál

Dokumentácia k nabíjaciemu systému EV a dashboardu **EV & Energia** v Home Assistant.

> Stručne: systém riadi **kedy a koľko** nabíjať elektromobil cez OCPP nabíjačku
> (`hacharger`) podľa solárnych prebytkov, tarify a cieľa, a zaznamenáva každú
> nabíjaciu **session** do CSV/XLSX s analytikou na dashboarde.

---

## 1. Balíky a súbory

| Súbor | Čo robí |
|---|---|
| `packages/ev_control.yaml` | Riadiaca logika — režimy, cieľový prúd, blok/pauza, regulácia prúdu (30 s) |
| `packages/ev_session.yaml` | Sledovanie session — štart/tick/stop, energia, cena, solar/grid split |
| `packages/ev_stats.yaml` | Ovládanie dashboardu Sessions — obdobie, metrika, filter áut |
| `packages/ev_autorecover.yaml` | **Plugin** (on/off): auto-detekcia zaseknutého nabíjania |
| `scripts/ev_sessions_json.py` | Agreguje CSV → JSON pre `sensor.ev_sessions_table` (graf, tabuľka) |
| `scripts/ev_export_xlsx.py` | Export CSV → naformátovaný XLSX |
| `scripts/ev_log_session.sh` | Zápis ukončenej session do CSV (volané z ev_session.yaml) |
| `scripts/ev_write_stats.sh` | Zápis výberu obdobia/metriky/filtra do `.ev_stats.json` |
| `dashboards/ev_energy.yaml` | Dashboard „EV & Energia" (YAML-mode) |
| `ev_sessions.csv` | História session (`www/ev_sessions.csv` = kópia pre /local download) |

---

## 2. Režimy nabíjania (`input_select.ev_charge_mode`)

| Režim | Správanie |
|---|---|
| **Fast** | Maximálny prúd (`ev_solar_max_current`, napr. 32 A). Ignoruje tarifu aj prebytky. |
| **Min+Solar** | Vždy aspoň minimálny prúd, navyšuje o prebytky (do max). |
| **Solar** | Len z prebytkov. Pod minimom (≈ Min prúd × 230 V) **pauza**. |
| **Vyp** | Nenabíjať (manuálny blok). |

**Cieľový prúd** (`sensor.ev_target_current`) = podľa režimu:
- Solar: `prebytok / 230 V`, ale len ak ≥ Min prúd, inak **0** (pauza).
- Min+Solar: `max(Min, prebytok/230)`, do Max.
- Fast: Max.

Reguláciu vykonáva automatizácia **„EV - Regulácia prúdu"** každých 30 s: keď je
`Charging`, nie je blok, tarifa povolená a cieľ ≥ 6 A → nastaví
`number.hacharger_maximum_current` na cieľový prúd.

### Cieľ (`input_select.ev_target_type`)
- **Žiadny** — nabíja bez limitu.
- **SOC** — do `ev_soc_limit` % (`sensor.mysan_battery_level`).
- **Range** — do `ev_target_range_km` (`sensor.mysan_estimated_range`).
- **kWh** — dobiť `ev_kwh_limit` kWh **tejto session** (`input_number.ev_session_energy_kwh`).

Pri dosiahnutí cieľa → `sensor.ev_target_reached = true` → blok `target`.

### Plán nabíjania (`packages/ev_schedule.yaml`)
Jeden plán, ktorý o štarte **aplikuje svoj režim + cieľ** do hlavného ovládania a uvoľní blok.
- **Zapnuté** (`input_boolean.ev_scheduled_enabled`), **Režim** (`ev_plan_mode`),
  **Opakovať** (`ev_plan_repeat`: Raz/Denne).
- **Časovanie** (`ev_plan_timing`):
  - **Štart o** — nabíjanie začne o `ev_scheduled_time`.
  - **Hotové do** — deadline `ev_scheduled_time` + **nabíjací prúd** `ev_plan_current` (A) →
    `sensor.ev_plan_start_time` **dopočíta čas štartu** (potreba kWh z cieľa a 40 kWh Leaf).
- **Nabíjací prúd** (`ev_plan_current`): o štarte sa nastaví ako `ev_solar_max_current`
  (reguluje prúd vo Fast aj ako strop v Solar/Min+Solar) + slúži na výpočet „Hotové do".
- **Cieľ** (`ev_plan_target`): Žiadny / SOC / Dojazd / kWh (hodnoty: `ev_soc_limit`,
  `ev_target_range_km`, `ev_plan_kwh`).
- **Bez pauzy pri zapnutí**: zapnutie plánu **NEzastaví** aktuálne nabíjanie. Cez deň pokračuje
  napr. Solar (slabé slnko dobije málo); o štarte sa len **prepne režim** a dobije zo siete.
  `input_boolean.ev_cable_connected` sleduje pripojený kábel aj cez solar-pauzy (status Unavailable).
- **Štart** (`ev_plan_start`): o `sensor.ev_plan_start_time` nastaví režim + cieľ a **zabezpečí
  nabíjanie** (uvoľní blok; ak nenabíja, spustí — bežiace nepreruší). **Raz** → po štarte vypne plán.
- Súhrn: `sensor.ev_plan_summary`. ⚠️ V noci nevoľ Solar (= 0 A) — pre nočné dobíjanie zo siete **Fast**.

Typický scenár: cez deň slabé slnko → Solar dobije pár kWh; plán „Štart o 22:00, Fast, SOC 100 %,
Denne" → po 22:00 (lacná tarifa) dobije zvyšok zo siete na ráno.

### Skip tarify (`input_boolean.ev_skip_t1..t4`)
Ak je aktívna tarifa označená ako skip → blok `tariff`, obnova keď nastane povolená tarifa.

---

## 3. Stavový automat — blok/pauza

`input_select.ev_block_reason`: `none | surplus | tariff | target | schedule | manual`

- **STOP** = `switch.hacharger_availability` OFF → 2 s → `switch.hacharger_charge_control` OFF
  (spoľahlivé na čistej transakcii).
- **START** = `switch.hacharger_availability` ON (auto si vyžiada transakciu).

Príklad (Solar pauza): prebytok klesne pod prah `ev_solar_pause_threshold_w` →
`block_reason = surplus`, availability OFF, charge_control OFF, `ev_charging_blocked = on`.
Obnova: prebytok nad `ev_solar_resume_threshold_w` na 3 min → availability ON, odblok.

---

## 4. Sledovanie session (`ev_session.yaml`)

Session = od pripojenia (stav `Charging`) po odpojenie. Každú minútu počas `Charging`
sa inkrementuje:
- **Energia** (kWh) — presne z delta kumulatívneho metra
  `sensor.hacharger_energy_active_import_register`.
- **Cena** (€) — `+= delta_kWh × cena aktuálnej tarify` (`sensor.ev_cena_kwh`).
- **Solar / grid split** — `solar = clamp(min(brutto_export, PV_výkon) / nabíjanie, 0..1)`.
  Strop PV je dôležitý: v noci výboj batérie tlačí grid do exportu — bez PV stropu
  by sa to počítalo ako solar. **PV = 0 → solar 0.**
- **Per-tarifa kWh** (T1–T4), **čas nabíjania** (len keď `Charging`).
- SOC štart/koniec, odometer — **len pre vozidlo `mysan`** (ostatné autá nemajú
  senzory → prázdne).

Po stope (energia > 0): zápis riadku do `ev_sessions.csv` cez
`shell_command.ev_log_session` → `scripts/ev_log_session.sh` (+ kópia do `www/`,
+ obnova XLSX). Notifikácia „EV Session ukončená".

> **Pozn.:** HA `shell_command` pri template-och nespúšťa cez shell, preto je
> zápis CSV v dedikovanom `.sh` skripte (nie inline `&&`/`;`/`>>`).

### CSV formát (20 stĺpcov)
`session_id, start, end, user, energy_kwh, charging_min, cost_eur, avg_price,
solar_kwh, grid_kwh, solar_pct, t1_kwh, t2_kwh, t3_kwh, t4_kwh,
soc_start, soc_end, odo_start, odo_end, stop_reason`

---

## 5. Dashboard „EV & Energia"

### Pohľad 1 — Prehľad
Gauge (Batéria, Dojazd), **Stav** (Nabíjačka, Tarifa, Cena, SOC, SOH, Odometer),
**Energetický tok** (FVE/Dom/Sieť/Prebytok/Nabíjanie), **Ovládanie nabíjania**
(režim, vozidlo, cieľ), **Vynechať tarify**, **Manuál & diagnostika**, **Prúd & solar prahy**.

### Pohľad 2 — Sessions
- **Prepínač obdobia**: Mesiac / Rok / Celkom + navigácia «» (`ev_stats_period`, `ev_stats_offset`).
- **Prepínač metriky**: ☀️ Solar (kWh) / € Cena (`ev_stats_metric`) — klientsky, prepína graf aj donut.
- **Graf** (button-card HTML) — denné/mesačné stĺpce slnko vs sieť, sleduje obdobie.
  (apexcharts-card pre stĺpce vnucuje datetime os a nevie kategórie — preto vlastný HTML graf.)
- **Donut** — energia/náklady podľa auta (sleduje metriku).
- **Filter auta** — dynamický dropdown (autá z dát).
- **Tabuľka** session + **Export XLSX/CSV** (XLSX sa obnovuje po každej session;
  podržaním tlačidla ručná regenerácia).

Dáta dodáva `sensor.ev_sessions_table` (command_line, beh `ev_sessions_json.py`,
riadené `.ev_stats.json`). Pri zmene obdobia/filtra → automatizácia `ev_stats_refresh`
zapíše ctrl súbor a prepočíta senzor.

---

## 6. Obnova pri zaseknutí (recovery)

> **Overené 11.6.:** samotný cyklus transakcie (availability/charge_control) zaseknutý
> pilot ~6 A **nevylieči** — treba **OCPP reset** (reboot nabíjačky). „Nabíjačka povolená"
> sa po resete vracia do OFF, kým charger plne nenabehne, preto je dôležité **poradie**.

V „Manuál & diagnostika":
- **🔄 Obnova nabíjania** (`script.ev_restart_charging`) — plná sekvencia:
  OCPP reset → počkať na reconnect → odblok → `availability` ON → `charge_control` ON.
- **♻️ Reset nabíjačky (OCPP)** (`button.hacharger_reset`) — len samotný reboot (granulárne).

**Auto-recovery plugin** (`input_boolean.ev_autorecover`, default OFF):
`binary_sensor.ev_charging_stuck` = cieľ ≥ 10 A, auto ťahá ≤ 8 A, **a pilot
`mysan_charge_current_limit` ≤ 8 A** (charger NEdodáva nastavený prúd), > 5 min,
cieľ nedosiahnutý. Pilot-podmienka odlišuje **taper** (auto si samo znižuje blízko
plného → pilot VYSOKÝ → nie stuck) od reálneho zaseknutia (pilot ~6 A). → upozornenie
+ **Obnova nabíjania** (OCPP reset + štart; ~1 min reštart nabíjačky).

---

## 7. Kľúčové entity

| Entita | Význam |
|---|---|
| `sensor.hacharger_status_connector` | Stav konektora (Available/Preparing/**Charging**/Finishing/Faulted) |
| `sensor.hacharger_energy_active_import_register` | Kumulatívny kWh meter (zdroj pravdy pre energiu) |
| `number.hacharger_maximum_current` | Limit prúdu nastavený na nabíjačke (strop) |
| `sensor.mysan_charge_current` | Reálne ťahaný prúd autom (OVMS) |
| `sensor.mysan_charge_current_limit` | Prúd, ktorý auto „vidí" (pilot signál) |
| `switch.hacharger_charge_control` | RemoteStart/Stop transakcie |
| `switch.hacharger_availability` | ChangeAvailability (Operative/Inoperative) |
| `button.hacharger_reset` | OCPP reset (reboot nabíjačky) |
| `sensor.gw_surplus` / `gw_pv_power` / `gw_grid_power` | GoodWe prebytok / PV / sieť (+export/−import) |
| `sensor.ev_target_current` / `ev_tariff_allowed` / `ev_target_reached` | Riadiace senzory |

---

## 8. Troubleshooting

| Príznak | Príčina / riešenie |
|---|---|
| **Fast/limit vysoký, ale auto ťahá ~6 A** | Zaseknutý pilot nabíjačky → **♻️ OCPP Reset**. Over aj car-side max AC prúd (OVMS). |
| **„Start transaction failed: Rejected"** | Desync transakcie pri prepnutí režimu → 🔄 Reštart nabíjania alebo replug. |
| **Cieľový prúd = 0 A** | Solar režim + prebytok < ~Min prúd × 230 V (pauza). Prepni na Min+Solar/Fast. |
| **Session sa nezapisuje** | Skontroluj `ha core logs \| grep ev_log_session` (nesmie byť „Error running command"). |
| **Solar % v noci > 0** | Opravené stropom PV vo vzorci (PV=0 → 0 %). |
| **Graf prázdny po listovaní** | Si na prázdnom období (napr. minulý rok) — vráť sa «»/». |
| **Charger ukazuje „nie je nabíjanie" hoci nabíja** | Neobnovená stránka — hard-refresh (Ctrl+Shift+R). |
