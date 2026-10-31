#!/usr/bin/env bash
# The forward marker on the VPS (PREREG P12.0 / P12.1 / P12.2): the operator's act, run from
# this machine with the operator's own ssh key, beside poo-tape.service (A13.4). Installs
# forward.py + marker.py + families.json + leaders_2026-11-01.json as a systemd service that
# observes only (the tape, the leaders' public fills, the book), holds no key, places no
# order (S73), and writes marks_<date>.jsonl under /root/poo/marker/out.
#   SEED=<the day's amendment commit sha> bash rights_events/fixtures/agent_record/ops/poo_marker_vps.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VPS=root@66.135.15.102
SSH="ssh -o IdentitiesOnly=yes -o ConnectTimeout=20 -i $HOME/.ssh/id_ed25519"
: "${SEED:?SEED=<amendment commit sha> is required (the C1 seed, recorded on every row)}"
$SSH $VPS 'mkdir -p /root/poo/marker/out'
for f in forward.py marker.py families.json leaders_2026-11-01.json; do
  scp -o IdentitiesOnly=yes -i "$HOME/.ssh/id_ed25519" -q "$HERE/marker/$f" "$VPS:/root/poo/marker/$f"
done
$SSH $VPS "cat > /etc/systemd/system/poo-marker.service <<UNIT
[Unit]
Description=Proof of Outcome: the forward marker (PREREG P12; observation only, no key, no order)
After=network-online.target poo-tape.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/poo/marker
ExecStart=/usr/bin/python3 -I /root/poo/marker/forward.py --tape-dir /root/poo/tape --out-dir /root/poo/marker/out --seed $SEED --poll-seconds 60
Restart=always
RestartSec=10
StandardOutput=append:/root/poo/marker/poo-marker.log
StandardError=append:/root/poo/marker/poo-marker.log

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now poo-marker.service && sleep 15
sha256sum /root/poo/marker/forward.py /root/poo/marker/marker.py /root/poo/marker/families.json /root/poo/marker/leaders_2026-11-01.json
systemctl is-active poo-marker.service
systemctl show -p MainPID -p ActiveEnterTimestamp poo-marker.service
tail -n 5 /root/poo/marker/poo-marker.log
ls -la /root/poo/marker/out"
