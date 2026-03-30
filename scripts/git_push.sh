#!/bin/bash
cd /config
LOG="/config/www/git_push.log"

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
PUSH_OUTPUT=$(git push origin main 2>&1)
PUSH_EXIT=$?
echo "$PUSH_OUTPUT" >> "$LOG"

if [ $PUSH_EXIT -eq 0 ]; then
  echo "STATUS:ok" >> "$LOG"
else
  echo "PUSH_EXIT_CODE: $PUSH_EXIT" >> "$LOG"
  echo "STATUS:error" >> "$LOG"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - END" >> "$LOG"
