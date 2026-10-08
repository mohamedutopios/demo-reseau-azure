"""Démo peering — service interne du réseau « spoke » (bibliothèque standard uniquement).

Il n'a pas d'IP publique : il n'est joignable que depuis un réseau relié par peering.
GET /api/interne   réponse du service, avec l'adresse de l'appelant
"""
import json
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOSTNAME = socket.gethostname()


def private_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("168.63.129.16", 80))  # aucune donnée envoyée : sert à trouver l'IP locale
        return s.getsockname()[0]


IP = private_ip()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/interne"):
            self.send_json({
                "message": "Bonjour depuis le réseau spoke 👋",
                "service": {"hostname": HOSTNAME, "ip": IP},
                "appelant": self.client_address[0],
                "heure": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
            })
        else:
            self.send_json({"error": "introuvable"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
