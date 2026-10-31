#!/usr/bin/env bash
# Pull the VPS marker's day files (marks, signals, state) to fixtures/agent_record/vps/marker/
# (read-only on the VPS; the laptop pulls, as poo_tape_pull.sh does). Pinned by sha in the
# day's amendment when read.
#   bash rights_events/fixtures/agent_record/ops/poo_marker_pull.sh [YYYY-MM-DD ...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VPS=root@66.135.15.102
SCP="scp -o IdentitiesOnly=yes -i $HOME/.ssh/id_ed25519 -q"
mkdir -p "$HERE/vps/marker"
for day in "${@:-$(date -u +%F)}"; do
  for kind in marks signals; do
    if $SCP "$VPS:/root/poo/marker/out/${kind}_$day.jsonl" "$HERE/vps/marker/${kind}_$day.jsonl" 2>/dev/null; then
      echo "vps/marker/${kind}_$day.jsonl rows=$(wc -l < "$HERE/vps/marker/${kind}_$day.jsonl") sha256=$(sha256sum "$HERE/vps/marker/${kind}_$day.jsonl" | cut -d' ' -f1)"
    else
      echo "vps/marker/${kind}_$day.jsonl absent on the VPS"
    fi
  done
done
$SCP "$VPS:/root/poo/marker/out/marker_state.json" "$HERE/vps/marker/marker_state.json" && echo "vps/marker/marker_state.json sha256=$(sha256sum "$HERE/vps/marker/marker_state.json" | cut -d' ' -f1)"
