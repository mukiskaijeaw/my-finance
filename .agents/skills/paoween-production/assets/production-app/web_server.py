#!/usr/bin/env python3
"""Serve the app locally and inject its paired loopback API address."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, api_port, **kwargs):
        self.api_port = api_port
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path.lstrip("/")
        if path in ("dashboard.html", "dashboard-classic.html"):
            target = ROOT / path
            content = target.read_bytes()
            script = f'<script>window.PAOWEEN_API_BASE="http://127.0.0.1:{self.api_port}";</script>'.encode()
            content = content.replace(b"</head>", script + b"</head>", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        return super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--api-port", type=int, required=True)
    args = parser.parse_args()
    handler = partial(Handler, api_port=args.api_port)
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
