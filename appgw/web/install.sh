#!/usr/bin/env bash
# Démo Application Gateway — VM « web » : nginx sert le site vitrine.
# Le site appelle /api/produits : c'est l'Application Gateway qui envoie
# ce chemin vers la VM « api ».
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
export DEBIAN_FRONTEND=noninteractive

apt-get -o DPkg::Lock::Timeout=300 update -q
apt-get -o DPkg::Lock::Timeout=300 install -y -q nginx

cp "$DIR/index.html" /var/www/html/index.html
rm -f /var/www/html/index.nginx-debian.html
cat > /var/www/html/info.json <<EOF
{"hostname": "$(hostname)", "ip": "$(hostname -I | awk '{print $1}')"}
EOF

systemctl enable nginx
systemctl restart nginx
