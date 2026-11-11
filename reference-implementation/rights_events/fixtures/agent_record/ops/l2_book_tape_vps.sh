#!/usr/bin/env bash
# The book tape on the VPS (PREREG A42 R182-R183), authorized by the operator's word of 2026-11-11
# ("Authorize the VPS deploy of the capture"). Installs l2_book_tape.py as a systemd service that
# observes only (HyperLiquid's public info endpoint: outcomeMeta, l2Book, recentTrades), holds no key,
# places no order; and installs the publish script that copies its day files to the channel's l2/.
#   bash rights_events/fixtures/agent_record/ops/l2_book_tape_vps.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VPS=root@66.135.15.102
SSH="ssh -o IdentitiesOnly=yes -o ConnectTimeout=20 -o BatchMode=yes -i $HOME/.ssh/id_ed25519"
SCP="scp -o IdentitiesOnly=yes -o BatchMode=yes -i $HOME/.ssh/id_ed25519 -q"
$SSH $VPS 'mkdir -p /root/poo/l2 && cp -p /root/poo/publish.sh /root/poo/publish.sh.before_A42'
$SCP "$HERE/l2_book_tape.py" "$VPS:/root/poo/l2_book_tape.py"
$SCP "$HERE/poo_publish_vps.sh" "$VPS:/root/poo/publish.sh.A42"
$SSH $VPS "cat > /etc/systemd/system/poo-l2tape.service <<UNIT
[Unit]
Description=Proof of Outcome: the book tape (PREREG A42 R182; observation only, no key, no order)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/poo/l2
ExecStart=/usr/bin/python3 -I /root/poo/l2_book_tape.py --out-dir /root/poo/l2
Restart=always
RestartSec=10
MemoryMax=96M
Nice=10
StandardOutput=append:/root/poo/l2/poo-l2tape.log
StandardError=append:/root/poo/l2/poo-l2tape.log

[Install]
WantedBy=multi-user.target
UNIT
if grep -q \$'\r' /root/poo/l2_book_tape.py /root/poo/publish.sh.A42; then echo 'CRLF in an installed file: refusing'; exit 1; fi
bash -n /root/poo/publish.sh.A42 && chmod 755 /root/poo/publish.sh.A42 && mv /root/poo/publish.sh.A42 /root/poo/publish.sh
systemctl daemon-reload && systemctl enable --now poo-l2tape.service && sleep 25
sha256sum /root/poo/l2_book_tape.py /root/poo/publish.sh
systemctl is-active poo-l2tape.service poo-tape.service poo-marker.service
systemctl show -p MainPID -p ActiveEnterTimestamp -p MemoryCurrent poo-l2tape.service
wc -l /root/poo/l2/l2tape_*.jsonl
tail -n 3 /root/poo/l2/poo-l2tape.log 2>/dev/null || true
df -h /root | tail -1"
