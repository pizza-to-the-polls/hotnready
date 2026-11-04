#!/bin/bash
# E-Day 15-min auto-refresh — hotnready /midterm-volume/ (night of 2026-11-03)
# Re-armed ~8:55pm PT at the user's request, cutoff extended midnight PT → 2:00am PT
# Nov 4. The tick at/after CUTOFF pushes one FINAL refresh and then removes this
# job from the crontab (self-disarming). gen.py is the repo-canonical copy in
# tools/midterm-volume/, pointed at the /tmp working dirs via env overrides.
export HOME=/Users/duncombe
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
LOG=/tmp/hrwork/refresh.log
GEN=/tmp/hotnready-publish/tools/midterm-volume/gen.py
export HRWORK=/tmp/hrwork
export HRPUB=/tmp/hrpub/midterm-volume
export HROUT=/tmp/hrout/midterm-volume
STAMP=$(date +%Y%m%d%H%M)
CUTOFF=202611040200        # Nov 4 02:00 PT
FINAL=""
[ "$STAMP" -ge "$CUTOFF" ] && FINAL=" — final refresh, cron disarming"
echo "=== $STAMP run start ($(date))$FINAL" >> "$LOG"

# lock: skip if previous run still going (stale after 10 min)
LOCK=/tmp/hrwork/.lock
if [ -d "$LOCK" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCK") )) -lt 600 ]; then
  echo "=== $STAMP SKIP (previous run still going)" >> "$LOG"; exit 0
fi
rm -rf "$LOCK" && mkdir "$LOCK"

cd /tmp/hrwork || { echo "=== $STAMP FAIL (no /tmp/hrwork)" >> "$LOG"; exit 1; }
if ! python3 "$GEN" >> "$LOG" 2>&1; then
  echo "=== $STAMP GEN FAILED" >> "$LOG"; rmdir "$LOCK"; exit 1
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
  if git commit -q -m "Midterm volume: E-Day auto-refresh $ET_LBL ET$FINAL" >> "$LOG" 2>&1 \
     && git push --quiet origin main >> "$LOG" 2>&1; then
    echo "=== $STAMP pushed ($ET_LBL ET)" >> "$LOG"
  else
    echo "=== $STAMP PUSH FAILED" >> "$LOG"
  fi
fi
rmdir "$LOCK"

# disarm after cutoff — only once the final push has landed
if [ "$STAMP" -ge "$CUTOFF" ]; then
  crontab -l 2>/dev/null | grep -v 'hrwork/refresh.sh' | crontab - 2>/dev/null
  echo "=== $STAMP DISARMED (past $CUTOFF) — good night" >> "$LOG"
fi
echo "=== $STAMP done ($(date))" >> "$LOG"
exit 0