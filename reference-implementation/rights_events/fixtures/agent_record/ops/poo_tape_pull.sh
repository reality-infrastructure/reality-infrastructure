#!/usr/bin/env bash
# Pull the VPS tape's day files to the fixtures folder (read-only on the VPS; the laptop
# pulls, as hood's ops/pull.sh does). A pulled file is pinned by sha in the day's amendment.
#   bash rights_events/fixtures/agent_record/ops/poo_tape_pull.sh [YYYY-MM-DD ...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VPS=root@66.135.15.102
mkdir -p "$HERE/vps"
for day in "${@:-$(date -u +%F)}"; do
  scp -o IdentitiesOnly=yes -i "$HOME/.ssh/id_ed25519" -q "$VPS:/root/poo/tape/tape_MIDS_$day.jsonl" "$HERE/vps/tape_MIDS_$day.jsonl"
  echo "vps/tape_MIDS_$day.jsonl rows=$(wc -l < "$HERE/vps/tape_MIDS_$day.jsonl") sha256=$(sha256sum "$HERE/vps/tape_MIDS_$day.jsonl" | cut -d' ' -f1)"
done
