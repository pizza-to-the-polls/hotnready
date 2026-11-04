#!/bin/bash
# E-Day 15-min auto-refresh — hotnready /midterm-volume/ (night of 2026-11-03)
# Re-pulls prod DB, regenerates the whole page (e15 chart, comp chart, 2026 daily
# chart, table, callout, CSV), commits + pushes. Self-disarms after midnight PT
# by removing its own crontab line.
export HOME=/Users/duncombe
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
LOG=/tmp/hrwork/refresh.log
STAMP=$(date +%Y%m%d%H%M)
echo "=== $STAMP run start ($(date))" >> "$LOG"

# disarm: after midnight PT (Nov 4 00:00 local) remove this job from the crontab
if [ "$STAMP" -ge 202611040000 ]; then
  crontab -l 2>/dev/null | grep -v 'hrwork/refresh.sh' | crontab - 2>/dev/null
  echo "=== $STAMP DISARMED (past midnight PT)" >> "$LOG"
  exit 0
fi

# lock: skip if previous run still going (stale after 10 min)
LOCK=/tmp/hrwork/.lock
if [ -d "$LOCK" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCK") )) -lt 600 ]; then
  echo "=== $STAMP SKIP (previous run still going)" >> "$LOG"
  exit 0
fi
rm -rf "$LOCK" && mkdir "$LOCK"

cd /tmp/hrwork || { echo "=== $STAMP FAIL (no /tmp/hrwork)" >> "$LOG"; exit 1; }
if ! python3 gen.py >> "$LOG" 2>&1; then
  echo "=== $STAMP GEN FAILED" >> "$LOG"
  rmdir "$LOCK"
  exit 1
fi

cd /tmp/hotnready-publish || { echo "=== $STAMP FAIL (no repo clone)" >> "$LOG"; rmdir "$LOCK"; exit 1; }
git pull --rebase --quiet origin main >> "$LOG" 2>&1
cp /tmp/hrout/midterm-volume/index.html midterm-volume/index.html
cp /tmp/hrout/midterm-volume/data/midterm_volume.csv midterm-volume/data/midterm_volume.csv
git add midterm-volume
if git diff --cached --quiet; then
  echo "=== $STAMP no changes to publish" >> "$LOG"
else
  ET_LBL=$(TZ=America/New_York date +'%-I:%M%p')
  git commit -q -m "Midterm volume: E-Day auto-refresh $ET_LBL ET — 15-min intraday chart + all charts + CSV" >> "$LOG" 2>&1
  if git push --quiet origin main >> "$LOG" 2>&1; then
    echo "=== $STAMP pushed ($ET_LBL ET)" >> "$LOG"
  else
    echo "=== $STAMP PUSH FAILED" >> "$LOG"
  fi
fi
rmdir "$LOCK"
echo "=== $STAMP done ($(date))" >> "$LOG"