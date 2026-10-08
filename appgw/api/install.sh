#!/usr/bin/env bash
# Démo Application Gateway — VM « api » : installe l'API Python comme service systemd.
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)

cat > /etc/systemd/system/demo-api.service <<EOF
[Unit]
Description=Demo API catalogue
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 $DIR/api.py
WorkingDirectory=$DIR
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now demo-api.service
