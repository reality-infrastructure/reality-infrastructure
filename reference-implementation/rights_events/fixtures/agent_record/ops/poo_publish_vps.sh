#!/bin/bash
# Publishes the Proof of Outcome day files (tape, marker signals/marks, state, service health, and
# since A18 the arena fills tape) to the orphan branch vps/poo-files of the record repo. Hourly from
# cron. Read-only on /root/poo. No venue path.
# A17.8 (R109): arena page files are published as line-complete parts of at most 8 MiB written by
# /root/poo/arena_parts.py; the raw page files leave the tree; the index, state and cohort files
# publish whole. R111: git gc --auto after the push (gc.auto 256, pack.windowMemory 64m, pack.threads 1).
set -u
SRC=/root/poo; REPO=/root/poo-publish; PARTS=/root/poo/arena_parts.py
cd $REPO || exit 1
mkdir -p tape marker arena
cp -p $SRC/tape/tape_MIDS_*.jsonl tape/ 2>/dev/null
cp -p $SRC/marker/out/*.jsonl marker/ 2>/dev/null
cp -p $SRC/marker/leaders_*.json $SRC/marker/families.json $SRC/marker/out/marker_state.json marker/ 2>/dev/null
tail -n 400 $SRC/marker/poo-marker.log > marker/poo-marker.log.tail 2>/dev/null
# the book tape (A42 R183): day files verbatim under l2/; not listed in manifest.json (the routine's health check is unchanged)
mkdir -p l2
cp -p $SRC/l2/l2tape_*.jsonl l2/ 2>/dev/null
# the arena fills tape (A18 R93; A17.8 R109): every cohort directory; pages as parts, the rest verbatim
if [ -d $SRC/arena ]; then
  for d in $SRC/arena/cohorts $SRC/arena/2*; do
    [ -d "$d" ] || continue
    dst="arena/$(basename "$d")"; mkdir -p "$dst"
    for f in "$d"/*.json "$d"/*.jsonl; do
      [ -f "$f" ] || continue
      case "$(basename "$f")" in
        pages_fills_*.jsonl|pages_funding_*.jsonl) python3 -I $PARTS split "$f" "$dst" >/dev/null || echo "$(date -u +%FT%TZ) S96 split failed: $f" ;;
        *) cp -p "$f" "$dst/" ;;
      esac
    done
    rm -f "$dst"/pages_fills_*.jsonl "$dst"/pages_funding_*.jsonl   # R109: raw page files are not in the tree
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
git commit -q -m "poo-vps day files $(date -u +%FT%TZ)" && git push -q -u origin vps/poo-files && echo "$(date -u +%FT%TZ) pushed $(git rev-parse --short HEAD)" && git gc --auto -q
