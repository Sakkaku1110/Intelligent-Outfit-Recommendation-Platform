#!/usr/bin/env python3
"""Windows-side gateway for tablets and phones.

Other devices connect to this PC, and the gateway proxies requests to the
SS928 board. This avoids routing issues caused by Windows ICS or separated
Wi-Fi/Ethernet subnets.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class GatewayHandler(BaseHTTPRequestHandler):
    board_url = "http://192.168.137.2"

    def log_message(self, fmt: str, *args: object) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS,HEAD")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_HEAD(self) -> None:
        self.proxy(write_body=False)

    def do_GET(self) -> None:
        if self.path == "/__gateway":
            self.send_gateway_health()
            return
        self.proxy(write_body=True)

    def do_POST(self) -> None:
        self.proxy(write_body=True)

    def do_PUT(self) -> None:
        self.proxy(write_body=True)

    def do_DELETE(self) -> None:
        self.proxy(write_body=True)

    def send_gateway_health(self) -> None:
        body = (
            "{\n"
            '  "status": "ok",\n'
            f'  "board_url": "{self.board_url}"\n'
            "}\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy(self, write_body: bool) -> None:
        target = urllib.parse.urljoin(self.board_url.rstrip("/") + "/", self.path.lstrip("/"))
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() != "host"
        }
        request = urllib.request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP:
                        self.send_header(key, value)
                self.end_headers()
                if not write_body:
                    return
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    self.send_header(key, value)
            self.end_headers()
            if write_body:
                self.wfile.write(exc.read())
        except Exception as exc:
            body = ("Gateway cannot reach board: %s\n" % exc).encode("utf-8")
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if write_body:
                self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--board", default="http://192.168.137.2")
    args = parser.parse_args()

    GatewayHandler.board_url = args.board
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print("Smart wardrobe PC gateway listening on http://%s:%d" % (args.host, args.port), flush=True)
    print("Proxying board:", args.board, flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
