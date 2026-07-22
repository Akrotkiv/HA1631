# Changelog — EV & Energia

Záznam zmien a opráv, ktoré sme robili na nabíjacom systéme EV a dashboarde.
Najnovšie hore. (Manuál systému: [EV_ENERGIA.md](EV_ENERGIA.md))

---

## 2026-06-12

### Auto-recovery — oprava falošného poplachu pri taper
- **Bug:** v noci pri takmer plnej batérii (SOC 94 %, cieľ 95 %) auto prirodzene znižovalo
  prúd (BMS taper) → detekcia zaseknutia to mylne vyhodnotila ako stuck (cieľ 32 A, reálne 7 A)
  a spustila zbytočný OCPP reset.
- **Rozlíšenie:** pri taper-i je **pilot `mysan_charge_current_limit` VYSOKÝ** (~27 A — charger
  ponúka, auto si berie menej); pri reálnom stuck-u je pilot ~6 A (charger nedodáva).
- **Fix:** `binary_sensor.ev_charging_stuck` teraz vyžaduje aj **pilot ≤ 8 A**. Taper (pilot
  vysoký) sa už nepovažuje za zaseknutie.

## 2026-06-11

### Plán nabíjania — parametrický (nahradil jednoduchý „Plánované nabíjanie")
- Nový balík `packages/ev_schedule.yaml`: jeden plán s **[režim][časovanie][cieľ][opakovať]**.
  - **Režim**: Fast / Min+Solar / Solar (aplikuje sa o štarte do `ev_charge_mode`).
  - **Časovanie**: „Štart o" (pevný čas) alebo „Hotové do" (deadline + predpokl. prúd A →
    `sensor.ev_plan_start_time` **dopočíta a zobrazí** čas štartu; potreba kWh z 40 kWh Leaf).
  - **Cieľ**: Žiadny / SOC / Dojazd / **kWh** (kWh = dobiť X kWh tejto session;
    pridané do `ev_target_type` + `ev_target_reached`, nový `ev_kwh_limit`).
  - **Opakovať**: Raz (po štarte vypne) / Denne.
- **Bez pauzy pri zapnutí** (revízia): plán **NEzastaví** aktuálne nabíjanie — cez deň beží napr.
  Solar a o štarte sa len prepne režim (dobije zo siete v lacnej tarife). `ev_cable_tracker` +
  `input_boolean.ev_cable_connected` sledujú pripojený kábel aj cez solar-pauzy (status Unavailable),
  aby plán o štarte vedel, že auto je pripojené. `ev_plan_start` bežiace nabíjanie nepreruší.
- Starý `ev_scheduled_start` odstránený (nahradený `ev_plan_start`). Dashboard karta „Plán nabíjania".
- **Self-heal pri štarte** (live test 11.6. 22:10): plán korektne spustil štart, ale charger
  poslal OCPP „Rejected" (flakovitý charger). `ev_plan_start` teraz po 90 s overí — ak charger
  nenabíja, spustí `script.ev_restart_charging` (OCPP reset + štart). Skript dostal **dlhšie
  čakanie po resete + retry RemoteStart** (prvý po resete býva odmietnutý, druhý prejde — overené).

### Solar % v noci — oprava
- **Bug:** session v noci ukazovali 30 %/70 % solar (PV = 0). Vzorec
  `solar = grid_export / nabíjanie` počítal **výboj domácej batérie ako solar**.
- **Fix:** `solar = clamp(min(brutto_export, PV_výkon) / nabíjanie, 0..1)` —
  strop PV (`sensor.gw_pv_power`). V noci PV = 0 → solar 0.
  (`packages/ev_session.yaml`)
- Opravené aj 2 historické nočné session (solar → grid, pct → 0).

### Obnova pri zaseknutí nabíjania
- **Diagnostika:** Fast nabehol na limit 32 A, ale auto ťahalo len ~6 A celú noc
  (`mysan_charge_current` ~5.9 A; 9.6. dokázalo 26 A). Zaseknutý **pilot signál**
  nabíjačky — neaplikuje nastavený limit. „Start transaction Rejected" bol sprievodný príznak.
- **Pridané:**
  - `script.ev_restart_charging` + tlačidlo **🔄 Obnova nabíjania**.
  - Tlačidlo **♻️ Reset nabíjačky (OCPP)** (`button.hacharger_reset`) — reboot, lieči zaseknutý pilot.
  - **Plugin `packages/ev_autorecover.yaml`** (default OFF): `binary_sensor.ev_charging_stuck`
    + automatizácia — pri cieli ≥ 10 A a reálne ≤ 8 A > 5 min upozorní + spustí obnovu.
    Izolované, vypínateľné cez `input_boolean.ev_autorecover`.
- **Live test (potvrdené):** jemný reštart transakcie **NEpomohol** (drží ~6 A / 1.3 kW),
  **OCPP reset áno** → nabehlo na 5.9 kW. „Nabíjačka povolená (OCPP)" sa po resete vracia
  do OFF, kým charger plne nenabehne — preto poradie *reset → počkať na reconnect →
  odblok → availability ON → charge_control ON*. **Recovery skript upgradnutý** presne na
  túto sekvenciu (button + auto-recovery ju teraz robia samé).
- **Dokumentácia:** pridaný manuál `docs/EV_ENERGIA.md` + tento changelog.

---

## 2026-06-08

### evcc-štýl analytika na dashboarde Sessions (stredná verzia)
- **Prepínač metriky** ☀️ Solar (kWh) / € Cena (`input_select.ev_stats_metric`) —
  graf aj donut sa prepínajú klientsky.
- **Cena v grafe** — bucket-y nesú aj `cost`; pri Cena metrika stĺpce = náklad
  rozdelený podľa slnko/sieť.
- **Donut „podľa auta"** (button-card SVG) — energia/náklady per auto, sleduje metriku.
- **Filter tabuľky podľa auta** — dynamický dropdown, autá z dát
  (`sensor.ev_sessions_table.vehicles` → `input_select.ev_stats_vehicle` cez automatizáciu).
- **Jednotky + väčšie písmo** na hodnotách grafu (€ / kWh).
- **XLSX export** — `scripts/ev_export_xlsx.py` (openpyxl), tlačidlo **Stiahnuť XLSX**,
  auto-obnova po každej session. (Google Sheets sync = fáza 2, čaká na Google credentials.)
- **walterpe = WalterPe** zjednotené v CSV.
- `scripts/ev_sessions_json.py`: `cost` v bucketoch, `by_vehicle`, `vehicles`, filter tabuľky.

### Grafy — oprava vykreslenia
- **Bug:** apexcharts-card pre stĺpce **vnucuje datetime os** a ignoruje kategórie →
  os X ukazovala epoch-ms, stĺpce neviditeľné.
- **Fix:** graf prekreslený cez **button-card HTML/CSS** z period-aware atribútu `chart`.
  Sleduje Mesiac/Rok/Celkom aj «». Skript vypĺňa všetky dni/mesiace.

### CSV download link — oprava
- **Bug:** markdown odkaz na `/local/...` pohltil HA SPA router (zobrazil default dashboard).
- **Fix:** tlačidlo `type: button` s `action: url` → otvorí súbor priamo.

---

## 2026-06-07

### Zápis session do CSV — kritická oprava
- **Bug:** od refaktoru (4.6.) sa session **nezapisovali** do `ev_sessions.csv`, hoci
  notifikácia prišla. `shell_command.ev_log_session` zlyhal s `return code 2`
  (`[: missing ]`) — HA `shell_command` pri template-och nespúšťa cez shell, takže
  inline `&&`/`;`/`>>`/`[` nefungovali.
- **Fix:** logika zápisu presunutá do `scripts/ev_log_session.sh` (volaný s 20 argumentmi),
  vzor ako ostatné funkčné `.sh` príkazy.
- **Backfill:** doplnené chýbajúce session (4.–7.6.); jedna poškodená (meter glitch
  81.5 kWh/15 min) vylúčená.

### Hardcoded mysan SOC/odometer pre cudzie autá
- **Bug:** stop automatizácia čítala `sensor.mysan_*` aj pre vojtesla → nezmyselné
  SOC/odo (napr. 86→80 %).
- **Fix:** SOC/odometer sa zapisujú **len pre vozidlo `mysan`**, inak prázdne.
  Opravené aj 2 spätne doplnené vojtesla riadky.

---

## Čaká / nápady (TODO)
- **Google Sheets sync** (fáza 2) — treba Google service-account JSON.
- Auto-recovery: po overení, že OCPP reset spoľahlivo obnoví nabíjanie, zvážiť
  eskaláciu (jemný reštart → ak stále zaseknuté → reset).
- Zvážiť čistejší per-vehicle stackovaný graf (plná evcc verzia).
