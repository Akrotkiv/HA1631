# Nasadenie opráv — krok za krokom

## Čo budeš potrebovať
- Prístup k HA cez **Samba** / **File Editor** / **SSH**
- Tento stiahnutý priečinok `HA1631_fixed/`

---

## KROK 1 — Nahraj súbory na HA

Celý priečinok `HA1631_fixed/` skopíruj na HA do:
```
/config/deploy/
```

**Cez Samba:** otvor `\\homeassistant\config\` a vytvor priečinok `deploy`, do neho všetko skopíruj.

**Cez File Editor addon:** vytvor `/config/deploy/` a nahraj súbory.

Po nahraní by si mal mať:
```
/config/deploy/
  ├── deploy.sh
  ├── configuration.yaml
  ├── automations.yaml
  ├── scripts.yaml
  ├── packages/
  │   └── ev_charging_tracking.yaml
  └── scripts/
      └── git_pull.sh
```

---

## KROK 2 — Spusti deploy

Otvor **Terminal & SSH** addon (alebo SSH) a spusti:

```bash
cd /config/deploy && bash deploy.sh
```

Script automaticky:
1. ✅ Vytvorí zálohu do `/config/backups/backup_XXXXX/`
2. ✅ Skopíruje opravené súbory
3. ✅ Skontroluje YAML syntax
4. ❌ Ak je chyba → automaticky vráti zálohu

---

## KROK 3 — Reštartuj HA

**Nastavenia → Systém → Reštartovať**

(Pred reštartom môžeš ísť do Vývojárske nástroje → YAML → Skontrolovať konfiguráciu)

---

## KROK 4 — Oprav dashboard EV (manuálne, 30 sekúnd)

Dashboard sa nedá nasadiť cez súbor, treba cez UI:

1. Otvor HA → záložka **EV**
2. Vpravo hore klikni **ceruzku** (editovať)
3. Nájdi kartu **📊 Aktuálna session**
4. Klikni na ňu → uprav entitu **Trvanie**
5. Zmeň `sensor.ev_session_trvanie_2` → `sensor.ev_session_trvanie`
6. Ulož

---

## KROK 5 — Nastav nové helpery

Po reštarte sa vytvoria nové helpery s predvolenými hodnotami.
Nastav ich podľa svojich potrieb:

| Helper | Odporúčaná hodnota | Kde |
|--------|-------------------|-----|
| Vetranie - CO2 prah vysoký | **1000** ppm | Nastavenia → Zariadenia → Helpery |
| Vetranie - CO2 prah nízky | **600** ppm | |
| Vetranie - Stupeň pri CO2 | **4** | |
| Vetranie - Auto-reštart čas | **08:00** | |
| Vetranie - Auto-reštart stupeň | **1** | |

A zapni prepínače:
- `Vetranie - CO2 automatizácia aktívna` → **ON** (ak chceš CO2 riadenie)
- `Vetranie - Automatický reštart` → **ON** (ak chceš auto-obnovenie po forced off)

---

## Hotovo! ✅

Po reštarte HA tvoj existujúci auto-push pošle zmeny na GitHub.
Predchádzajúca verzia zostane v git histórii (commit `7850712`).

---

## Ak niečo nefunguje — ROLLBACK

```bash
# Pozri dostupné zálohy:
ls /config/backups/

# Obnov zo zálohy:
cd /config/backups/backup_XXXXX/
cp configuration.yaml /config/
cp automations.yaml /config/
cp scripts.yaml /config/
cp packages/ev_charging_tracking.yaml /config/packages/

# Reštartuj HA
```
