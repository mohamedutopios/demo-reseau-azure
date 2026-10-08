#!/usr/bin/env bash
# Démo peering — VM du hub : nginx sert la page et relaie /api/ vers le
# service interne du spoke (10.50.1.4:8080), joignable seulement via le peering.
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
SPOKE_URL=${SPOKE_URL:-http://10.50.1.4:8080}
export DEBIAN_FRONTEND=noninteractive

apt-get -o DPkg::Lock::Timeout=300 update -q
apt-get -o DPkg::Lock::Timeout=300 install -y -q nginx

cp "$DIR/index.html" /var/www/html/index.html
rm -f /var/www/html/index.nginx-debian.html
cat > /var/www/html/info.json <<EOF
{"hostname": "$(hostname)", "ip": "$(hostname -I | awk '{print $1}')", "cible": "$SPOKE_URL"}
EOF

cat > /etc/nginx/sites-available/default <<EOF
server {
    listen 80 default_server;
    root /var/www/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ =404;
    }

    # Relais vers le service du spoke. Délais courts : sans peering,
    # la page affiche l'échec en 3 secondes au lieu d'attendre une minute.
    location /api/ {
        proxy_pass $SPOKE_URL;
        proxy_connect_timeout 3s;
        proxy_read_timeout 5s;
    }
}
EOF

nginx -t
systemctl enable nginx
systemctl restart nginx
