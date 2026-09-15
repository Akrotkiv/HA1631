# OCPP hotfix — HA Core 2026.6.0 kompatibilita (2026-09-15)

**Problém:** Po update HA Core na 2026.6.0 prestalo fungovať ovládanie nabíjačky
a EV session sa neukončovala ani nepočítala. Všetky OCPP entity (`sensor.hacharger_*`,
`switch.hacharger_*`, `number.hacharger_maximum_current`) boli `unavailable`, hoci
nabíjačka bola pripojená (`sensor.hacharger_heartbeat` sa aktualizoval).

**Príčina:** OCPP integrácia (`custom_components/ocpp`, v0.11.4) volá v `ChargePoint.update()`
`dr.async_get_devices(...)`, ktoré v `DeviceRegistry` HA Core 2026.6.0 už neexistuje →
`AttributeError` pri každom update cykle → entity sa nikdy neaktualizujú.

```
File "/config/custom_components/ocpp/chargepoint.py", line 699, in update
    dr.async_get_devices(...)
AttributeError: 'DeviceRegistry' object has no attribute 'async_get_devices'.
Did you mean: 'async_get_device'?
```

**Oprava** v `custom_components/ocpp/chargepoint.py`, funkcia `update()`:

```diff
-        root_dev = next(
-            iter(
-                dr.async_get_devices(
-                    identifiers=identifiers,
-                    config_entry_id=self.entry.entry_id,
-                )
-            ),
-            None,
-        )
+        root_dev = dr.async_get_device(identifiers=identifiers)
```

`async_get_device(identifiers=...)` vráti jediné zariadenie zhodné s ktorýmkoľvek
identifikátorom v množine (alebo `None`) — presne to, čo pôvodné `next(iter(...), None)`
získavalo. `config_entry_id` filter je zbytočný: identifikátory `(DOMAIN, cpid)` a
`(DOMAIN, self.id)` sú pre tento charge point jedinečné.

**Aplikovanie vyžaduje reštart HA Core** (reload config entry modul znovu nenačíta).

> POZN.: `custom_components/` je v `.gitignore`, takže samotný patch v gite nie je.
> HACS update OCPP integrácie tento fix prepíše — ak sa `AttributeError` vráti,
> znovu aplikuj vyššie uvedenú zmenu (alebo prejdi na verziu integrácie, ktorá to má
> opravené upstream).
