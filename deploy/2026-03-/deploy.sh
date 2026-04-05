#!/bin/bash
# ============================================
# DEPLOY - 6 opráv pre HA1631
# ============================================
# Všetky súbory sú v jednom adresári /config/deploy/
# Spusti: cd /config/deploy && bash deploy.sh
# ============================================

set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/config/backups/backup_${TIMESTAMP}"
D="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================"
echo "  HA1631 - Nasadenie 6 opráv"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Kontrola
for f in configuration.yaml automations.yaml scripts.yaml ev_charging_tracking.yaml git_pull.sh; do
  if [ ! -f "$D/$f" ]; then
    echo "❌ Chýba súbor: $D/$f"
    exit 1
  fi
done
echo "✅ Všetky súbory nájdené"
echo ""

# 1. ZÁLOHA
echo "📦 [1/4] Záloha..."
mkdir -p "$BACKUP_DIR/packages" "$BACKUP_DIR/scripts"
cp /config/configuration.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ configuration.yaml"
cp /config/automations.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ automations.yaml"
cp /config/scripts.yaml "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ scripts.yaml"
cp /config/packages/ev_charging_tracking.yaml "$BACKUP_DIR/packages/" 2>/dev/null && echo "  ✅ packages/ev_charging_tracking.yaml"
cp /config/scripts/git_pull.sh "$BACKUP_DIR/scripts/" 2>/dev/null || true
echo "  → Záloha: $BACKUP_DIR"
echo ""

# 2. KOPÍROVANIE
echo "🔧 [2/4] Kopírovanie..."
cp "$D/configuration.yaml" /config/configuration.yaml && echo "  ✅ configuration.yaml"
cp "$D/automations.yaml" /config/automations.yaml && echo "  ✅ automations.yaml"
cp "$D/scripts.yaml" /config/scripts.yaml && echo "  ✅ scripts.yaml"
cp "$D/ev_charging_tracking.yaml" /config/packages/ev_charging_tracking.yaml && echo "  ✅ → packages/ev_charging_tracking.yaml"
cp "$D/git_pull.sh" /config/scripts/git_pull.sh && chmod +x /config/scripts/git_pull.sh && echo "  ✅ → scripts/git_pull.sh"
echo ""

# 3. YAML KONTROLA
echo "🔍 [3/4] Kontrola YAML..."
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
  echo "  ✅ Záloha obnovená. Nič sa nezmenilo."
  exit 1
fi
echo ""

# 4. HOTOVO
echo "============================================"
echo "  ✅ HOTOVO!"
echo "============================================"
echo ""
echo "  Teraz reštartuj HA:"
echo "  Nastavenia → Systém → Reštart"
echo ""
echo "  Po reštarte v dashboarde EV oprav:"
echo "  sensor.ev_session_trvanie_2 → sensor.ev_session_trvanie"
echo ""
echo "  ROLLBACK keby niečo:"
echo "  cp $BACKUP_DIR/configuration.yaml /config/"
echo "  cp $BACKUP_DIR/automations.yaml /config/"
echo "  cp $BACKUP_DIR/scripts.yaml /config/"
echo "  cp $BACKUP_DIR/packages/ev_charging_tracking.yaml /config/packages/"
echo ""
