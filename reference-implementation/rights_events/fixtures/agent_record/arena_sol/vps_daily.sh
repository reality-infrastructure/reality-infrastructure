#!/usr/bin/env bash
# The arena on Solana, the daily read on the VPS (PREREG A48 R229). Installing it is the operator's act.
# Reads yesterday (UTC) for the cohort's graded wallets from the public node, then grades as of today.
# A day already pinned is not read again. Cron, once a day after 00:30Z:
#   35 0 * * * /path/to/reference-implementation/rights_events/fixtures/agent_record/arena_sol/vps_daily.sh S1 >> ~/arena_sol.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
COHORT="${1:-S1}"
ROOT="$(cd ../../../.. && pwd)"
DAY="$(date -u -d 'yesterday' +%F)"
TODAY="$(date -u +%F)"
T0="$(python3 -c "import json,glob;print(json.load(open(glob.glob('$COHORT/capture_SOL_*.json')[0]))['window']['t0_date'])")"
T1="$(python3 -c "import json,glob;print(json.load(open(glob.glob('$COHORT/capture_SOL_*.json')[0]))['window']['t1_date'])")"
echo "$(date -u +%FT%TZ) $COHORT: through $DAY, window $T0 .. $T1"
D="$T0"
while [[ ! "$D" > "$DAY" && ! "$D" > "$T1" ]]; do        # every finished window day not yet pinned: a missed day is read late
  if [[ -f "$COHORT/days/$D/MANIFEST.json" ]]; then
    echo "$D already pinned"
  else
    python3 -u read_sol_day.py --cohort-dir "$COHORT" --day "$D"
  fi
  D="$(date -u -d "$D + 1 day" +%F)"
done
cd "$ROOT" && python3 -m rights_events.sol_arena grade --cohort-dir "rights_events/fixtures/agent_record/arena_sol/$COHORT" --as-of "$TODAY"
