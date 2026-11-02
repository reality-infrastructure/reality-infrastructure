#!/bin/bash
# Publishes the Proof of Outcome day files (tape, marker signals/marks, state, service health) to the
# orphan branch vps/poo-files of the record repo. Hourly from cron. Read-only on /root/poo. No venue path.
set -u
SRC=/root/poo; REPO=/root/poo-publish
cd $REPO || exit 1
mkdir -p tape marker
cp -p $SRC/tape/tape_MIDS_*.jsonl tape/ 2>/dev/null
cp -p $SRC/marker/out/*.jsonl marker/ 2>/dev/null
cp -p $SRC/marker/leaders_*.json $SRC/marker/families.json $SRC/marker/out/marker_state.json marker/ 2>/dev/null
tail -n 400 $SRC/marker/poo-marker.log > marker/poo-marker.log.tail 2>/dev/null
NEWEST=$(ls -t $SRC/tape/tape_MIDS_*.jsonl | head -1)
{
  printf "{\"generated_at\":\"%s\",\"poo_tape\":\"%s\",\"poo_marker\":\"%s\",\"tape_newest_mtime\":\"%s\",\"tape_newest_file\":\"%s\",\"files\":[" \
    "$(date -u +%FT%TZ)" "$(systemctl is-active poo-tape)" "$(systemctl is-active poo-marker)" "$(date -u -r "$NEWEST" +%FT%TZ)" "$(basename "$NEWEST")"
  first=1
  for f in tape/* marker/*; do
    [ $first = 1 ] || printf ","; first=0
    printf "{\"name\":\"%s\",\"bytes\":%s,\"sha256\":\"%s\",\"mtime\":\"%s\"}" "$f" "$(stat -c %s "$f")" "$(sha256sum "$f" | cut -d" " -f1)" "$(date -u -r "$f" +%FT%TZ)"
  done
  printf "]}\n"
} > manifest.json
git add -A
if git diff --cached --quiet; then echo "$(date -u +%FT%TZ) nothing new"; exit 0; fi
git commit -q -m "poo-vps day files $(date -u +%FT%TZ)" && git push -q -u origin vps/poo-files && echo "$(date -u +%FT%TZ) pushed $(git rev-parse --short HEAD)"
