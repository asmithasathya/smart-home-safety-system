#!/usr/bin/env python3
"""
MeshGuard UART Agent

Run this on a teammate laptop when that laptop has exactly one project board
plugged in. The agent reads the local UART and forwards each log line to the
main MeshGuard command center over Wi-Fi.
"""

from __future__ import annotations

import argparse
import glob
import json
import signal
import subprocess
import sys
import threading
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_NAMES = ("controller", "light", "alarm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward one board UART to MeshGuard.")
    parser.add_argument(
        "--source",
        choices=SOURCE_NAMES,
        help="Which board is plugged into this laptop.",
    )
    parser.add_argument(
        "--port",
        help="Local UART port, usually /dev/cu.usbmodemXXXX.",
    )
    parser.add_argument(
        "--command-center",
        help="Base dashboard URL printed by the main laptop, for example http://192.168.1.20:8420.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="UART baud rate (default: 115200).",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Optional token matching command center --ingest-token.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Print visible /dev/cu.usbmodem* ports and exit.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not echo forwarded UART lines locally.",
    )
    parser.add_argument(
        "--heartbeat-sec",
        type=float,
        default=3.0,
        help="Seconds between connection heartbeats (default: 3.0).",
    )
    return parser.parse_args()


def list_ports() -> List[str]:
    return sorted(glob.glob("/dev/cu.usbmodem*"))


def ingest_url(command_center: str) -> str:
    cleaned = command_center.rstrip("/")
    if cleaned.endswith("/api/ingest"):
        return cleaned
    return cleaned + "/api/ingest"


def post_payload(url: str, payload: dict, token: str, quiet_errors: bool = False) -> bool:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=2.0) as response:
            return 200 <= response.status < 300
    except HTTPError as exc:
        if not quiet_errors:
            print(f"[uart-agent] Command center rejected payload: HTTP {exc.code}", file=sys.stderr)
    except URLError as exc:
        if not quiet_errors:
            print(f"[uart-agent] Could not reach command center: {exc.reason}", file=sys.stderr)
    except TimeoutError:
        if not quiet_errors:
            print("[uart-agent] Command center request timed out", file=sys.stderr)
    return False


def post_line(url: str, source: str, line: str, token: str) -> bool:
    return post_payload(url, {"source": source, "line": line}, token)


def post_heartbeat(url: str, source: str, token: str) -> bool:
    return post_payload(
        url,
        {"source": source, "heartbeat": True},
        token,
        quiet_errors=True,
    )


def require_args(args: argparse.Namespace) -> None:
    missing = [
        name
        for name in ("source", "port", "command_center")
        if not getattr(args, name)
    ]
    if missing:
        joined = ", ".join("--" + name.replace("_", "-") for name in missing)
        raise SystemExit(f"Missing required argument(s): {joined}")


def main() -> int:
    args = parse_args()

    if args.list_ports:
        ports = list_ports()
        if ports:
            print("\n".join(ports))
        else:
            print("No /dev/cu.usbmodem* ports found.")
        return 0

    require_args(args)
    url = ingest_url(args.command_center)

    stty_result = subprocess.run(
        ["stty", "-f", args.port, str(args.baud), "raw", "-echo"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if stty_result.returncode != 0:
        print(
            f"[uart-agent] Could not open UART {args.port}: {stty_result.stderr.strip()}",
            file=sys.stderr,
        )
        return 2

    process: Optional[subprocess.Popen[str]] = None
    stop_event = threading.Event()

    def stop(_sig: int, _frame: object) -> None:
        stop_event.set()
        if process and process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(f"[uart-agent] Forwarding {args.source} UART {args.port}")
    print(f"[uart-agent] Command center: {url}")

    def heartbeat_loop() -> None:
        post_heartbeat(url, args.source, args.token)
        while not stop_event.wait(args.heartbeat_sec):
            post_heartbeat(url, args.source, args.token)

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    try:
        process = subprocess.Popen(
            ["cat", args.port],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            if not args.quiet:
                print(f"[{args.source}] {line}")
            post_line(url, args.source, line, args.token)
    except OSError as exc:
        print(f"[uart-agent] UART reader failed: {exc}", file=sys.stderr)
        return 2
    finally:
        stop_event.set()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
