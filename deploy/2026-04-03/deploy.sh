#!/bin/bash
# ============================================
# DEPLOY v2 - HA1631 opravy
# ============================================
# Všetky súbory v jednom adresári /config/deploy/
# Spusti: cd /config/deploy && bash deploy.sh
# ============================================

set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/config/backups/backup_${TIMESTAMP}"
D="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================"
echo "  HA1631 - Deploy v2"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Kontrola súborov
MISSING=0
for f in configuration.yaml automations.yaml scripts.yaml ev_charging_tracking.yaml; do
  if [ ! -f "$D/$f" ]; then echo "❌ Chýba: $f"; MISSING=1; fi
done
if [ "$MISSING" = "1" ]; then exit 1; fi
echo "✅ Všetky súbory nájdené"
echo ""

# 1. ZÁLOHA
echo "📦 [1/5] Záloha..."
mkdir -p "$BACKUP_DIR/packages" "$BACKUP_DIR/scripts"
cp /config/configuration.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ configuration.yaml"
cp /config/automations.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ automations.yaml"
cp /config/scripts.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ scripts.yaml"
cp /config/packages/ev_charging_tracking.yaml "$BACKUP_DIR/packages/" 2>/dev/null && echo "  ✅ ev_charging_tracking.yaml"
cp /config/scripts/ev_generate_report.py "$BACKUP_DIR/scripts/" 2>/dev/null && echo "  ✅ ev_generate_report.py"
cp /config/.storage/lovelace "$BACKUP_DIR/lovelace_storage" 2>/dev/null && echo "  ✅ .storage/lovelace (dashboard)"
echo "  → Záloha: $BACKUP_DIR"
echo ""

# 2. KOPÍROVANIE CONFIG SÚBOROV
echo "🔧 [2/5] Kopírovanie config..."
cp "$D/configuration.yaml" /config/configuration.yaml && echo "  ✅ configuration.yaml"
cp "$D/automations.yaml" /config/automations.yaml && echo "  ✅ automations.yaml"
cp "$D/scripts.yaml" /config/scripts.yaml && echo "  ✅ scripts.yaml"
cp "$D/ev_charging_tracking.yaml" /config/packages/ev_charging_tracking.yaml && echo "  ✅ → packages/ev_charging_tracking.yaml"
echo ""

# 3. KOPÍROVANIE SCRIPTOV
echo "📜 [3/5] Kopírovanie scriptov..."
if [ -f "$D/git_pull.sh" ]; then
  cp "$D/git_pull.sh" /config/scripts/git_pull.sh && chmod +x /config/scripts/git_pull.sh && echo "  ✅ → scripts/git_pull.sh"
fi
if [ -f "$D/ev_generate_report.py" ]; then
  cp "$D/ev_generate_report.py" /config/scripts/ev_generate_report.py && echo "  ✅ → scripts/ev_generate_report.py"
fi
echo ""

# 4. YAML KONTROLA
echo "🔍 [4/5] YAML kontrola..."
YAML_OK=true
python3 -c "
import yaml, sys
class L(yaml.SafeLoader): pass
L.add_constructor('!include', lambda l,n: l.construct_scalar(n))
L.add_constructor('!include_dir_merge_named', lambda l,n: l.construct_scalar(n))
L.add_constructor('!secret', lambda l,n: l.construct_scalar(n))
err=0
for f in ['configuration.yaml','automations.yaml','scripts.yaml','packages/ev_charging_tracking.yaml']:
    try:
        with open(f'/config/{f}') as fh: yaml.load(fh,Loader=L)
        print(f'  ✅ {f}')
    except Exception as e:
        print(f'  ❌ {f}: {e}'); err+=1
sys.exit(err)
" 2>&1 || YAML_OK=false

if [ "$YAML_OK" = false ]; then
  echo ""
  echo "  ❌ YAML CHYBA! Obnovovanie zálohy..."
  cp "$BACKUP_DIR/configuration.yaml" /config/
  cp "$BACKUP_DIR/automations.yaml" /config/
  cp "$BACKUP_DIR/scripts.yaml" /config/
  cp "$BACKUP_DIR/packages/ev_charging_tracking.yaml" /config/packages/
  echo "  ✅ Záloha obnovená."
  exit 1
fi
echo ""

# 5. DASHBOARD
echo "🖥️  [5/5] Dashboard..."
if [ -f "$D/lovelace_default.json" ]; then
  cp "$D/lovelace_default.json" /config/.storage/lovelace && echo "  ✅ Dashboard nasadený (.storage/lovelace)"
  echo "  ℹ️  Dashboard sa načíta po reštarte HA"
else
  echo "  ⏭️  Dashboard JSON nenájdený - preskočené"
fi
echo ""

# HOTOVO
echo "============================================"
echo "  ✅ HOTOVO! Teraz reštartuj HA."
echo "============================================"
echo ""
echo "  Po reštarte nastav helpery (ak ešte nie sú):"
echo "    vetranie_co2_threshold_high  = 1000 ppm"
echo "    vetranie_co2_threshold_low   = 600 ppm"
echo "    vetranie_co2_stupen          = 4"
echo "    vetranie_auto_restart_time   = 08:00"
echo "    vetranie_auto_restart_stupen = 1"
echo ""
echo "  ROLLBACK keby niečo:"
echo "    cp $BACKUP_DIR/configuration.yaml /config/"
echo "    cp $BACKUP_DIR/automations.yaml /config/"
echo "    cp $BACKUP_DIR/scripts.yaml /config/"
echo "    cp $BACKUP_DIR/packages/ev_charging_tracking.yaml /config/packages/"
echo "    cp $BACKUP_DIR/lovelace_storage /config/.storage/lovelace"
echo "    # a reštart HA"
echo ""
