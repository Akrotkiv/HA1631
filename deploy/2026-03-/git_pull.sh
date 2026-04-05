#!/bin/bash
# ============================================
# GIT PULL - Stiahne zmeny z GitHubu do HA
# ============================================
cd /config
LOG="/config/www/git_pull.log"

export GIT_SSH_COMMAND="ssh -i /config/.ssh/ha_github -o StrictHostKeyChecking=accept-new"

echo "$(date '+%Y-%m-%d %H:%M:%S') - PULL START" > "$LOG"

# Uložiť lokálne zmeny
git stash >> "$LOG" 2>&1

# Pull z remote
git pull origin main >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  echo "STATUS:ok" >> "$LOG"
else
  echo "STATUS:error" >> "$LOG"
  git stash pop >> "$LOG" 2>&1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - PULL END" >> "$LOG"
