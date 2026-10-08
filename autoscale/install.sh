#!/usr/bin/env bash
# Démo autoscaling — installe le serveur Python comme service systemd.
# Lancé par cloud-init (Custom data) sur CHAQUE instance du Scale Set,
# y compris celles créées plus tard par l'autoscaling.
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)

cat > /etc/systemd/system/demo-autoscale.service <<EOF
[Unit]
Description=Demo autoscaling
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 $DIR/server.py
WorkingDirectory=$DIR
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now demo-autoscale.service
