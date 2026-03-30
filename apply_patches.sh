#!/bin/bash
# =============================================
# PATCH pre ev_charging_tracking.yaml
# Aplikuj na /config/packages/ev_charging_tracking.yaml
# =============================================
# POZOR: Spusti kazdy blok JEDNOTLIVO a over vysledok!
# =============================================

cd /config/packages

# 1. ZALOHA
cp ev_charging_tracking.yaml ev_charging_tracking.yaml.bak_$(date +%Y%m%d_%H%M%S)

# =============================================
# PATCH 1: Pridaj input_number.ev_last_session_duration_min
# (za ev_soc_limit blok)
# =============================================

sed -i '/^  ev_soc_limit:$/,/^    mode: slider$/{
  /^    mode: slider$/a\
\
  ev_last_session_duration_min:\
    name: "EV - Posledna session trvanie (min)"\
    min: 0\
    max: 99999\
    step: 0.1\
    unit_of_measurement: "min"\
    icon: mdi:timer-check\
    mode: box
}' ev_charging_tracking.yaml

echo "PATCH 1 done: ev_last_session_duration_min"

# =============================================
# PATCH 2: Pridaj shell_command pre reporty
# (za ev_copy_csv_to_www)
# =============================================

sed -i "/ev_copy_csv_to_www:.*$/a\\
\\
  # Report generatory\\
  ev_generate_monthly_report: 'python3 /config/scripts/ev_generate_report.py monthly'\\
  ev_generate_yearly_report: 'python3 /config/scripts/ev_generate_report.py yearly'\\
  ev_generate_xlsx_report: 'python3 /config/scripts/ev_generate_report.py xlsx'\\
  ev_refresh_csv: 'python3 /config/scripts/ev_generate_report.py refresh'" ev_charging_tracking.yaml

echo "PATCH 2 done: shell_commands"

# =============================================
# PATCH 3: Fix ev_session_trvanie - zobraz poslednu session ked sa nenabija
# Nahrad cely else blok
# =============================================

python3 << 'PYEOF'
import re

with open('ev_charging_tracking.yaml', 'r') as f:
    content = f.read()

# Najdi a nahrad trvanie sensor - else cast
old = """          {% else %}
            00:00
          {% endif %}
        icon: mdi:timer-outline"""

new = """          {% else %}
            {% set mins = states('input_number.ev_last_session_duration_min') | float(0) %}
            {% set hours = (mins // 60) | int %}
            {% set minutes = (mins % 60) | int %}
            {{ '%02d:%02d' | format(hours, minutes) }}
          {% endif %}
        icon: mdi:timer-outline"""

if old in content:
    content = content.replace(old, new, 1)
    print("PATCH 3 done: ev_session_trvanie fixed")
else:
    print("PATCH 3 SKIP: pattern not found (maybe already patched?)")

with open('ev_charging_tracking.yaml', 'w') as f:
    f.write(content)
PYEOF

# =============================================
# PATCH 4: Fix ev_charging_stopped - pridaj debounce 3 min
# =============================================

python3 << 'PYEOF'
with open('ev_charging_tracking.yaml', 'r') as f:
    content = f.read()

old_trigger = """    trigger:
      - platform: state
        entity_id: sensor.hacharger_status_connector
        from: "Charging"
    condition:
      - condition: state
        entity_id: input_boolean.ev_charging_active
        state: "on"
    action:
      - service: script.ev_end_session
        data:
          stop_reason: >
            {% if trigger.to_state.state == 'Available' %}
              ev_disconnected
            {% elif trigger.to_state.state == 'Finishing' %}
              completed
            {% elif trigger.to_state.state == 'Faulted' %}
              error
            {% else %}
              manual
            {% endif %}"""

new_trigger = """    trigger:
      - platform: state
        entity_id: sensor.hacharger_status_connector
        from: "Charging"
        for:
          minutes: 3
    condition:
      - condition: state
        entity_id: input_boolean.ev_charging_active
        state: "on"
      - condition: not
        conditions:
          - condition: state
            entity_id: sensor.hacharger_status_connector
            state: "Charging"
    action:
      - service: script.ev_end_session
        data:
          stop_reason: >
            {% set status = states('sensor.hacharger_status_connector') %}
            {% if status == 'Available' %}
              ev_disconnected
            {% elif status == 'Finishing' %}
              completed
            {% elif status == 'Faulted' %}
              error
            {% else %}
              manual
            {% endif %}"""

if old_trigger in content:
    content = content.replace(old_trigger, new_trigger, 1)
    print("PATCH 4 done: debounce 3min added to ev_charging_stopped")
else:
    print("PATCH 4 SKIP: pattern not found")

with open('ev_charging_tracking.yaml', 'w') as f:
    f.write(content)
PYEOF

# =============================================
# PATCH 5: Uloz trvanie v ev_end_session pred vypnutim flagu
# =============================================

python3 << 'PYEOF'
with open('ev_charging_tracking.yaml', 'r') as f:
    content = f.read()

# Najdi miesto pred "Vypni flag" / "input_boolean.turn_off" v ev_end_session
old_turnoff = """      # Skopíruj CSV do www pre download
      - service: shell_command.ev_copy_csv_to_www
      
      # Vypni flag
      - service: input_boolean.turn_off"""

new_turnoff = """      # Skopíruj CSV do www pre download
      - service: shell_command.ev_copy_csv_to_www
      
      # Uloz trvanie poslednej session
      - service: input_number.set_value
        target:
          entity_id: input_number.ev_last_session_duration_min
        data:
          value: "{{ duration_min }}"
      
      # Vypni flag
      - service: input_boolean.turn_off"""

if old_turnoff in content:
    content = content.replace(old_turnoff, new_turnoff, 1)
    print("PATCH 5 done: duration saved before turn_off")
else:
    print("PATCH 5 SKIP: pattern not found")

with open('ev_charging_tracking.yaml', 'w') as f:
    f.write(content)
PYEOF

# =============================================
# PATCH 6: Pridaj report skripty pred automations
# =============================================

python3 << 'PYEOF'
with open('ev_charging_tracking.yaml', 'r') as f:
    content = f.read()

new_scripts = """
  # ========================================
  # REPORT SKRIPTY
  # ========================================
  ev_generate_monthly_report:
    alias: "EV - Mesacny report"
    mode: single
    sequence:
      - service: shell_command.ev_generate_monthly_report
      - delay:
          seconds: 3
      - service: persistent_notification.create
        data:
          title: "EV Report"
          message: "Mesacny report vygenerovany. /local/ev_reports/"
          notification_id: ev_monthly_report

  ev_generate_yearly_report:
    alias: "EV - Rocny report"
    mode: single
    sequence:
      - service: shell_command.ev_generate_yearly_report
      - delay:
          seconds: 3
      - service: persistent_notification.create
        data:
          title: "EV Report"
          message: "Rocny report vygenerovany. /local/ev_reports/"
          notification_id: ev_yearly_report

  ev_generate_xlsx_report:
    alias: "EV - XLSX report"
    mode: single
    sequence:
      - service: shell_command.ev_generate_xlsx_report
      - delay:
          seconds: 5
      - service: persistent_notification.create
        data:
          title: "EV Report"
          message: "XLSX report vygenerovany."
          notification_id: ev_xlsx_report

  ev_refresh_csv:
    alias: "EV - Refresh CSV"
    mode: single
    sequence:
      - service: shell_command.ev_refresh_csv
      - service: shell_command.ev_copy_csv_to_www

"""

# Pridaj pred "# ================================\n# AUTOMATIONS"
marker = "# ================================\n# AUTOMATIONS"
if marker in content and "ev_generate_monthly_report:" not in content:
    content = content.replace(marker, new_scripts + marker, 1)
    print("PATCH 6 done: report scripts added")
else:
    if "ev_generate_monthly_report:" in content:
        print("PATCH 6 SKIP: already present")
    else:
        print("PATCH 6 FAIL: marker not found")

with open('ev_charging_tracking.yaml', 'w') as f:
    f.write(content)
PYEOF

echo ""
echo "=== VSETKY PATCHE APLIKOVANE ==="
echo "Teraz restartuj HA: Settings -> System -> Restart"