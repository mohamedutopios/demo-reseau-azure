"""Démo Application Gateway — API catalogue (bibliothèque standard uniquement).

GET /api/health     état de l'API (cible de la sonde d'intégrité)
GET /api/produits   catalogue de produits
Tout autre chemin   404 — y compris « / », ce qui est voulu pour la démo des sondes.
"""
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOSTNAME = socket.gethostname()


def private_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("168.63.129.16", 80))  # aucune donnée envoyée : sert à trouver l'IP locale
        return s.getsockname()[0]


IP = private_ip()

PRODUITS = [
    {"nom": "Casque audio", "description": "Réduction de bruit active", "prix": 129.90, "emoji": "🎧", "couleur": "#e8e0ff"},
    {"nom": "Clavier mécanique", "description": "Switches silencieux", "prix": 89.00, "emoji": "⌨️", "couleur": "#ffe3ec"},
    {"nom": "Souris ergonomique", "description": "Verticale, sans fil", "prix": 49.50, "emoji": "🖱️", "couleur": "#dff6ea"},
    {"nom": "Écran 27 pouces", "description": "QHD, 165 Hz", "prix": 299.00, "emoji": "🖥️", "couleur": "#e0efff"},
    {"nom": "Webcam HD", "description": "1080p, micro intégré", "prix": 59.90, "emoji": "📷", "couleur": "#fff1d6"},
    {"nom": "Station d'accueil", "description": "USB-C, 11 ports", "prix": 139.00, "emoji": "🔌", "couleur": "#f0f0f0"},
]


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            self.send_json({"status": "ok", "hostname": HOSTNAME})
        elif path == "/api/produits":
            self.send_json({"servi_par": {"hostname": HOSTNAME, "ip": IP}, "produits": PRODUITS})
        else:
            self.send_json({"error": "introuvable", "path": path}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
