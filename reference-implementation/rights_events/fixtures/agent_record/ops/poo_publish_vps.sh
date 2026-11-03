#!/bin/bash
# Publishes the Proof of Outcome day files (tape, marker signals/marks, state, service health, and
# since A18 the arena fills tape) to the orphan branch vps/poo-files of the record repo. Hourly from
# cron. Read-only on /root/poo. No venue path.
set -u
SRC=/root/poo; REPO=/root/poo-publish
cd $REPO || exit 1
mkdir -p tape marker arena
cp -p $SRC/tape/tape_MIDS_*.jsonl tape/ 2>/dev/null
cp -p $SRC/marker/out/*.jsonl marker/ 2>/dev/null
cp -p $SRC/marker/leaders_*.json $SRC/marker/families.json $SRC/marker/out/marker_state.json marker/ 2>/dev/null
tail -n 400 $SRC/marker/poo-marker.log > marker/poo-marker.log.tail 2>/dev/null
# the arena fills tape (A18 R93): every cohort directory, pages verbatim, index, state, cohort files
if [ -d $SRC/arena ]; then
  for d in $SRC/arena/cohorts $SRC/arena/2*; do
    [ -d "$d" ] || continue
    mkdir -p "arena/$(basename "$d")"
    cp -p "$d"/*.json "$d"/*.jsonl "arena/$(basename "$d")/" 2>/dev/null
  done
  tail -n 200 $SRC/arena/poo-arena-tape.log > arena/poo-arena-tape.log.tail 2>/dev/null
fi
NEWEST=$(ls -t $SRC/tape/tape_MIDS_*.jsonl | head -1)
{
  printf "{\"generated_at\":\"%s\",\"poo_tape\":\"%s\",\"poo_marker\":\"%s\",\"poo_arena_tape_timer\":\"%s\",\"tape_newest_mtime\":\"%s\",\"tape_newest_file\":\"%s\",\"files\":[" \
    "$(date -u +%FT%TZ)" "$(systemctl is-active poo-tape)" "$(systemctl is-active poo-marker)" "$(systemctl is-active poo-arena-tape.timer)" "$(date -u -r "$NEWEST" +%FT%TZ)" "$(basename "$NEWEST")"
  first=1
  for f in tape/* marker/* $(find arena -type f 2>/dev/null | sort); do
    [ -f "$f" ] || continue
    [ $first = 1 ] || printf ","; first=0
    printf "{\"name\":\"%s\",\"bytes\":%s,\"sha256\":\"%s\",\"mtime\":\"%s\"}" "$f" "$(stat -c %s "$f")" "$(sha256sum "$f" | cut -d" " -f1)" "$(date -u -r "$f" +%FT%TZ)"
  done
  printf "]}\n"
} > manifest.json
git add -A
if git diff --cached --quiet; then echo "$(date -u +%FT%TZ) nothing new"; exit 0; fi
git commit -q -m "poo-vps day files $(date -u +%FT%TZ)" && git push -q -u origin vps/poo-files && echo "$(date -u +%FT%TZ) pushed $(git rev-parse --short HEAD)"
