#!/usr/bin/env python3
"""
SIH-DETA Web Server Launcher
Serves the SIH-DETA progress dashboard and project portal.
Provides local network and SSH tunnel guidance for remote viewing.
"""

import http.server
import socket
import socketserver
import sys
import urllib.request
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
PREFERRED_PORTS = [8080, 8000, 8888, 5000, 3000, 8081, 8082]


def find_free_port(ports):
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    # Fallback to ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_public_ip():
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            continue
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, format, *args):
        # Clean timestamped access logs
        sys.stderr.write(f"[SIH-DETA HTTP] {self.address_string()} - {format % args}\n")


def main():
    port = find_free_port(PREFERRED_PORTS)
    local_ip = get_local_ip()
    public_ip = get_public_ip()
    hostname = socket.gethostname()

    print("=" * 75)
    print("  🚆 SIH-DETA DASHBOARD & PROJECT WEB SERVER")
    print("=" * 75)
    print(f"  • Serving Directory: {DIRECTORY}")
    print(f"  • Listening Port:    {port}")
    print(f"  • Host Machine:      {hostname}")
    print(f"  • Internal IP:       {local_ip}")
    if public_ip:
        print(f"  • Public IP:         {public_ip}")
    print("=" * 75)
    print("  🌐 HOW TO VIEW ON YOUR LAPTOP:")
    print("=" * 75)
    print()
    print("  👉 OPTION 1: SSH Port Forwarding (Recommended - works anywhere / behind firewalls)")
    print("     Run this command in a terminal on your LAPTOP:")
    print(f"       ssh -N -L {port}:localhost:{port} <your-ssh-user>@{public_ip or hostname}")
    print()
    print(f"     Then open this URL in your laptop browser:")
    print(f"       👉 http://localhost:{port}")
    print()
    if public_ip:
        print("  👉 OPTION 2: Direct Global Access (If server firewall/security group allows incoming traffic)")
        print(f"     Open in any browser directly:")
        print(f"       👉 http://{public_ip}:{port}")
        print()
    print(f"  👉 OPTION 3: Direct LAN/VPN Access (If your laptop is on the same VPN or subnet):")
    print(f"     Open in your laptop browser:")
    print(f"       👉 http://{local_ip}:{port}")
    print("=" * 75)
    print("  Server is active and listening for incoming connections...")
    print("  Press Ctrl+C anytime to stop.")
    print("=" * 75)
    sys.stdout.flush()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    main()
