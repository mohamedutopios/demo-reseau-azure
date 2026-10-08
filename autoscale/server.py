"""Démo autoscaling — petit serveur web (bibliothèque standard uniquement).

GET  /             page de démonstration
GET  /api/info     identité de l'instance + CPU instantané
POST /api/stress   sature tous les cœurs de l'instance qui reçoit la requête (?minutes=N)
POST /api/stop     arrête la charge sur l'instance qui reçoit la requête
"""
import json
import os
import socket
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).parent
PORT = int(os.getenv("PORT", "80"))
MAX_MINUTES = 15

stress_procs: list[subprocess.Popen] = []
stress_until = 0.0


def imds_zone() -> str:
    req = urllib.request.Request(
        "http://169.254.169.254/metadata/instance/compute/zone?api-version=2021-02-01&format=text",
        headers={"Metadata": "true"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.read().decode() or "aucune"
    except OSError:
        return "inconnue"


ZONE = imds_zone()
HOSTNAME = socket.gethostname()


def cpu_percent(interval: float = 0.5) -> float:
    def snapshot():
        values = list(map(int, Path("/proc/stat").read_text().split("\n")[0].split()[1:]))
        idle = values[3] + values[4]
        return idle, sum(values)

    idle1, total1 = snapshot()
    time.sleep(interval)
    idle2, total2 = snapshot()
    busy = (total2 - total1) - (idle2 - idle1)
    return round(100 * busy / max(total2 - total1, 1), 1)


def stress_active() -> bool:
    return any(p.poll() is None for p in stress_procs)


def start_stress(minutes: int) -> None:
    global stress_procs, stress_until
    if stress_active():
        return
    seconds = minutes * 60
    stress_procs = [
        subprocess.Popen(["timeout", str(seconds), "sh", "-c", "while :; do :; done"])
        for _ in range(os.cpu_count() or 1)
    ]
    stress_until = time.time() + seconds


def stop_stress() -> None:
    global stress_until
    for p in stress_procs:
        if p.poll() is None:
            p.kill()
    stress_until = 0


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 : la connexion est fermée après chaque réponse,
    # donc chaque requête peut être répartie vers une autre instance.
    protocol_version = "HTTP/1.0"

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def info(self):
        active = stress_active()
        return {
            "hostname": HOSTNAME,
            "zone": ZONE,
            "cpu": cpu_percent(),
            "cores": os.cpu_count(),
            "stress": active,
            "stress_remaining_s": max(0, int(stress_until - time.time())) if active else 0,
        }

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/info":
            self.send_json(self.info())
        elif path == "/health":
            self.send_json({"status": "ok"})
        else:
            self.send_json({"error": "introuvable"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/stress":
            minutes = int(parse_qs(url.query).get("minutes", ["10"])[0])
            start_stress(max(1, min(minutes, MAX_MINUTES)))
            self.send_json(self.info())
        elif url.path == "/api/stop":
            stop_stress()
            self.send_json(self.info())
        else:
            self.send_json({"error": "introuvable"}, 404)

    def log_message(self, fmt, *args):
        pass  # pas de journal par requête : la page interroge le serveur en continu


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
