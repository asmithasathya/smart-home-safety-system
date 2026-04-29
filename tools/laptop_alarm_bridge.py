#!/usr/bin/env python3
"""
UART-to-speaker alarm bridge for Smart Home Safety System.

Listens for:
  - "ALERT: ACTIVE" -> start repeating alarm sound
  - "ALERT: CLEAR"  -> stop alarm sound

macOS primary path: afplay (built-in)
"""

from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
from typing import Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play laptop alarm from board UART logs."
    )
    parser.add_argument(
        "--port",
        help="Serial port (example: /dev/cu.usbmodem10577409961)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="UART baud rate (default: 115200)",
    )
    parser.add_argument(
        "--sound",
        default="alarm.m4a",
        help="Sound file to play with afplay (default: alarm.m4a in repo root)",
    )
    parser.add_argument(
        "--cooldown-ms",
        type=int,
        default=800,
        help="Minimum ms between retriggers while already active",
    )
    parser.add_argument(
        "--test-sound",
        action="store_true",
        help="Play the configured sound once and exit",
    )
    return parser.parse_args()


class AlarmPlayer:
    def __init__(self, sound_path: str) -> None:
        self.sound_path = sound_path
        self._active = False
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._child: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()
            print("[bridge] Alarm sound started")

    def stop(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._stop_event.set()
            self._terminate_child()
            print("[bridge] Alarm sound stopped")

    def close(self) -> None:
        self.stop()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1.0)

    def _terminate_child(self) -> None:
        if self._child and self._child.poll() is None:
            self._child.terminate()
            try:
                self._child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._child.kill()
        self._child = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._child = subprocess.Popen(
                    ["afplay", self.sound_path],
                )
                ret = self._child.wait()
                if ret != 0 and not self._stop_event.is_set():
                    print(f"[bridge] afplay exited with code {ret}", file=sys.stderr)
                    time.sleep(0.2)
            except FileNotFoundError:
                print("[bridge] afplay not found; exiting alarm loop", file=sys.stderr)
                return
            except Exception as exc:  # pragma: no cover
                print(f"[bridge] Alarm playback error: {exc}", file=sys.stderr)
                time.sleep(0.2)


def main() -> int:
    args = parse_args()
    if not shutil.which("afplay"):
        print("afplay is not available on PATH.", file=sys.stderr)
        return 2

    if not os.path.exists(args.sound):
        print(f"Sound file not found: {args.sound}", file=sys.stderr)
        return 2

    if args.test_sound:
        print(f"[bridge] Test-playing: {args.sound}")
        ret = subprocess.run(["afplay", args.sound]).returncode
        return ret

    if not args.port:
        print("Missing --port (required unless --test-sound is used)", file=sys.stderr)
        return 2

    try:
        import serial  # type: ignore
    except ImportError:
        print(
            "Missing dependency: pyserial\nInstall with: pip install pyserial",
            file=sys.stderr,
        )
        return 2

    alarm = AlarmPlayer(args.sound)
    shutting_down = False
    last_trigger_ms = 0

    def shutdown_handler(_sig: int, _frame: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        alarm.close()
        print("\n[bridge] Exiting...")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"[bridge] Opening {args.port} @ {args.baud}")
    print(f"[bridge] Sound file: {args.sound}")

    try:
        with serial.Serial(args.port, args.baud, timeout=0.2) as ser:
            while not shutting_down:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                print(f"[uart] {line}")
                now_ms = int(time.time() * 1000)

                upper_line = line.upper()
                if "ALERT:" in upper_line and "ACTIVE" in upper_line:
                    if now_ms - last_trigger_ms >= args.cooldown_ms:
                        print("[bridge] Trigger: ALERT ACTIVE")
                        alarm.start()
                        last_trigger_ms = now_ms
                elif "ALERT:" in upper_line and "CLEAR" in upper_line:
                    print("[bridge] Trigger: ALERT CLEAR")
                    alarm.stop()
    except Exception as exc:
        alarm.close()
        print(f"[bridge] Serial error: {exc}", file=sys.stderr)
        return 1

    alarm.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
