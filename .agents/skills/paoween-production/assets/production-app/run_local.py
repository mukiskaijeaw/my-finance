#!/usr/bin/env python3
"""Start Paoween on unused loopback ports without connecting to another install."""
import argparse
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def choose_port(preferred, used):
    for port in [preferred]:
        if port in used:
            continue
        with socket.socket() as sock:
            try:
                sock.bind((HOST, port))
                used.add(port)
                return port
            except OSError:
                pass
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        port = sock.getsockname()[1]
    while port in used:
        with socket.socket() as sock:
            sock.bind((HOST, 0))
            port = sock.getsockname()[1]
    used.add(port)
    return port


def ready(url, headers=None):
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    args = parser.parse_args()
    used = set()
    web_port = choose_port(8765, used)
    api_port = choose_port(8766, used)
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, str(ROOT / "dashboard_server.py"), "--bind", HOST, "--port", str(api_port), "--web-port", str(web_port)], cwd=ROOT))
        children.append(subprocess.Popen([sys.executable, str(ROOT / "web_server.py"), "--bind", HOST, "--port", str(web_port), "--api-port", str(api_port)], cwd=ROOT))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A local Paoween service exited during startup")
            origin = f"http://{HOST}:{web_port}"
            if ready(origin + "/database.csv") and ready(origin + "/tax_preparation.csv") and ready(f"http://{HOST}:{api_port}/api/copilot/status", {"Origin": origin}):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Paoween did not become ready within 15 seconds")
        url = f"http://{HOST}:{web_port}/"
        print(f"Paoween is running at {url} (Ctrl-C to stop).", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
