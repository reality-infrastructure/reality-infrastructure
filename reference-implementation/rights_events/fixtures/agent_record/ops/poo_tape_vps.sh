#!/usr/bin/env bash
# The environment tape on the VPS (PREREG A13.3 R71): the operator's act, run from this
# machine with the operator's own ssh key. Installs tape_mids.py as a systemd service that
# observes only (one allMids poll per 5 s for the declared coins), holds no key, places no
# order, and survives this laptop's sleeps, shutdowns and network drops.
#   bash rights_events/fixtures/agent_record/ops/poo_tape_vps.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VPS=root@66.135.15.102
SSH="ssh -o IdentitiesOnly=yes -o ConnectTimeout=20 -i $HOME/.ssh/id_ed25519"
COINS="${COINS:-BTC,ETH,HYPE,ZEC,SOL,NEAR}"
$SSH $VPS 'mkdir -p /root/poo/tape'
scp -o IdentitiesOnly=yes -i "$HOME/.ssh/id_ed25519" -q "$HERE/tape_mids.py" "$VPS:/root/poo/tape_mids.py"
$SSH $VPS "cat > /etc/systemd/system/poo-tape.service <<UNIT
[Unit]
Description=Proof of Outcome: the environment tape (PREREG A13 R70 / A13.3 R71; observation only, no key, no order)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/poo/tape
ExecStart=/usr/bin/python3 -I /root/poo/tape_mids.py --coins $COINS --poll-seconds 5 --hours 0 --out-dir /root/poo/tape
Restart=always
RestartSec=5
StandardOutput=append:/root/poo/tape/poo-tape.log
StandardError=append:/root/poo/tape/poo-tape.log

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now poo-tape.service && sleep 8
sha256sum /root/poo/tape_mids.py
systemctl is-active poo-tape.service
systemctl show -p MainPID -p ActiveEnterTimestamp poo-tape.service
tail -n 3 /root/poo/tape/poo-tape.log
wc -l /root/poo/tape/tape_MIDS_*.jsonl
head -c 240 /root/poo/tape/tape_MIDS_\$(date -u +%F).jsonl; echo"
