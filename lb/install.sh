#!/usr/bin/env bash
# Démo Load Balancer — installe nginx et publie une page qui affiche
# quel serveur a répondu à chaque requête.
# Lancé automatiquement par cloud-init (Custom data) au premier démarrage de la VM.
set -euxo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
export DEBIAN_FRONTEND=noninteractive

apt-get -o DPkg::Lock::Timeout=300 update -q
apt-get -o DPkg::Lock::Timeout=300 install -y -q nginx

# Identité de la VM, lue sur le service de métadonnées Azure (IMDS)
ZONE=$(curl -s -H Metadata:true \
  "http://169.254.169.254/metadata/instance/compute/zone?api-version=2021-02-01&format=text" || true)
cat > /var/www/html/info.json <<EOF
{"hostname": "$(hostname)", "zone": "${ZONE:-aucune}", "ip": "$(hostname -I | awk '{print $1}')"}
EOF

cp "$DIR/index.html" /var/www/html/index.html
rm -f /var/www/html/index.nginx-debian.html

# Pas de keep-alive : chaque requête ouvre une nouvelle connexion TCP,
# que le Load Balancer peut envoyer vers une autre VM.
sed -i 's/^\s*keepalive_timeout .*/\tkeepalive_timeout 0;/' /etc/nginx/nginx.conf

systemctl enable nginx
systemctl restart nginx
