#!/usr/bin/env bash
# Démo peering — VM du spoke : installe le service interne (port 8080) comme service systemd.
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)

cat > /etc/systemd/system/demo-interne.service <<EOF
[Unit]
Description=Demo service interne (spoke)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 $DIR/service.py
WorkingDirectory=$DIR
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now demo-interne.service
