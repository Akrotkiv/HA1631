#!/bin/bash
cd /config
LOG="/config/www/git_push.log"

export GIT_SSH_COMMAND="ssh -i /config/.ssh/ha_github -o StrictHostKeyChecking=accept-new"

echo "$(date '+%Y-%m-%d %H:%M:%S') - START" > "$LOG"

git add -A >> "$LOG" 2>&1

if git diff --cached --quiet; then
  echo "Nič na commit - žiadne zmeny" >> "$LOG"
  echo "STATUS:no_changes" >> "$LOG"
  exit 0
fi

MSG="${1:-auto update $(date +%Y-%m-%d_%H:%M)}"
echo "Commit message: $MSG" >> "$LOG"

git commit -m "$MSG" >> "$LOG" 2>&1
git push origin main >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  echo "STATUS:ok" >> "$LOG"
else
  echo "STATUS:error" >> "$LOG"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - END" >> "$LOG"
