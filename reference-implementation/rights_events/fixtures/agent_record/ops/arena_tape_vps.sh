#!/usr/bin/env bash
# THE ARENA's fills tape on the VPS (PREREG A18 R93): the operator's act, run from this machine
# with the operator's own ssh key, beside poo-tape and poo-marker. Installs arena_fills_tape.py
# as a systemd service + hourly timer (observation only: no key, no order, S73), writes one
# cohort file per open cohort from the record's own arena captures, replaces /root/poo/publish.sh
# with the repo copy that also publishes arena/, and runs the first cycle.
#   bash rights_events/fixtures/agent_record/ops/arena_tape_vps.sh <cohort capture json> [...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VPS=root@66.135.15.102
SSH="ssh -o IdentitiesOnly=yes -o ConnectTimeout=20 -i $HOME/.ssh/id_ed25519"
SCP="scp -o IdentitiesOnly=yes -i $HOME/.ssh/id_ed25519 -q"
[ $# -ge 1 ] || { echo "usage: $0 <capture_ARENA_<cohort>_<cohort>.json> [...]"; exit 2; }
$SSH $VPS 'mkdir -p /root/poo/arena/cohorts'
$SCP "$HERE/ops/arena_fills_tape.py" "$VPS:/root/poo/arena/arena_fills_tape.py"
$SCP "$HERE/ops/poo_publish_vps.sh" "$VPS:/root/poo/publish.sh"
for cap in "$@"; do
  python - "$cap" > /tmp/cohort.json <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
co, w = d["cohort"], d["window"]
addrs = [a["address"].lower() for a in co["addresses"]]
actor = d["actor"]["actor_id"].lower()
if actor not in addrs:
    addrs.append(actor)
print(json.dumps({"cohort_date": co["cohort_date"], "t0_ms": w["t0_ms"], "t1_ms": w["t1_ms"],
                  "payload_sha256": co["payload_sha256"], "addresses": addrs}, indent=1))
EOF
  name="cohort_$(python -c "import json,sys; print(json.load(open(sys.argv[1]))['cohort']['cohort_date'])" "$cap").json"
  $SCP /tmp/cohort.json "$VPS:/root/poo/arena/cohorts/$name"
  echo "cohort file $name installed"
done
$SSH $VPS "chmod +x /root/poo/publish.sh /root/poo/arena/arena_fills_tape.py && sed -i 's/\r\$//' /root/poo/publish.sh /root/poo/arena/arena_fills_tape.py && cat > /etc/systemd/system/poo-arena-tape.service <<UNIT
[Unit]
Description=Proof of Outcome: the arena fills tape (PREREG A18 R93; observation only, no key, no order)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/root/poo/arena
ExecStart=/usr/bin/python3 -I /root/poo/arena/arena_fills_tape.py --root /root/poo/arena
StandardOutput=append:/root/poo/arena/poo-arena-tape.log
StandardError=append:/root/poo/arena/poo-arena-tape.log
UNIT
cat > /etc/systemd/system/poo-arena-tape.timer <<UNIT
[Unit]
Description=Proof of Outcome: the arena fills tape, hourly at :20

[Timer]
OnCalendar=*-*-* *:20:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload && systemctl enable --now poo-arena-tape.timer && systemctl start poo-arena-tape.service; sleep 2; systemctl is-active poo-arena-tape.timer; tail -5 /root/poo/arena/poo-arena-tape.log"
