#!/usr/bin/env python3
"""
MeshGuard Command Center

Runs a live laptop/phone dashboard for the Smart Home Safety System.

Features:
  - Serves a responsive web dashboard
  - Reads UART from multiple boards with built-in macOS tools (`stty` + `cat`)
  - Broadcasts live state to the browser with Server-Sent Events
  - Plays integrated desktop sounds with `afplay`
  - Exposes the same dashboard URL to phones on the local network
"""

from __future__ import annotations

import argparse
import glob
import json
import mimetypes
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboard"
ALERT_SOUND = ROOT / "ElevenLabs_glitchy,_staticky_radio-esque_threat_alert_sound.mp3"
NIGHT_SOUND = ROOT / "goodnight_sound.mp3"

SOURCE_NAMES = ("controller", "light", "alarm")
DISPLAY_NAMES = {
    "controller": "Entryway Controller",
    "light": "Living Room Light",
    "alarm": "Bedroom Alarm",
}
SIGNAL_DBM = {
    "controller": -67,
    "light": -52,
    "alarm": -41,
}
SIGNAL_PERCENT = {
    "controller": 76,
    "light": 88,
    "alarm": 81,
}
ROOM_LABELS = {
    "controller": "Entryway",
    "light": "Living Room",
    "alarm": "Bedroom",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MeshGuard command center.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="NAME=/dev/cu.usbmodemXXXX",
        help="Attach a UART source. NAME must be controller, light, or alarm.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Print visible /dev/cu.usbmodem* ports and exit.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="UART baud rate for all sources (default: 115200).",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="HTTP bind host (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8420,
        help="HTTP bind port (default: 8420).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run without UART sources and emit a looping mock demo.",
    )
    parser.add_argument(
        "--remote-only",
        action="store_true",
        help="Start without local UART sources and wait for remote UART agents.",
    )
    parser.add_argument(
        "--ingest-token",
        default="",
        help="Optional bearer token required for remote /api/ingest UART posts.",
    )
    parser.add_argument(
        "--desktop-audio",
        action="store_true",
        help="Play alert/night sounds on the laptop with afplay.",
    )
    parser.add_argument(
        "--alert-sound",
        default=str(ALERT_SOUND),
        help="Alert loop sound file served to browser and used for desktop audio.",
    )
    parser.add_argument(
        "--night-sound",
        default=str(NIGHT_SOUND),
        help="Night one-shot sound file served to browser and used for desktop audio.",
    )
    parser.add_argument(
        "--cooldown-ms",
        type=int,
        default=1000,
        help="Minimum ms between repeated alert sound retriggers.",
    )
    parser.add_argument(
        "--night-cooldown-ms",
        type=int,
        default=2400,
        help="Minimum ms between repeated Night sound triggers.",
    )
    return parser.parse_args()


def parse_sources(values: List[str]) -> Dict[str, str]:
    sources: Dict[str, str] = {}

    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --source value: {value!r}")
        name, port = value.split("=", 1)
        name = name.strip().lower()
        port = port.strip()
        if name not in SOURCE_NAMES:
            raise SystemExit(
                f"Invalid source name {name!r}. Expected one of: {', '.join(SOURCE_NAMES)}"
            )
        sources[name] = port

    return sources


def list_ports() -> List[str]:
    return sorted(glob.glob("/dev/cu.usbmodem*"))


def iso_now() -> float:
    return time.time()


def pretty_time(ts: float) -> str:
    return time.strftime("%I:%M:%S %p", time.localtime(ts)).lstrip("0")


def describe_system_label(mode: str, alert_active: bool, armed: bool) -> str:
    if alert_active:
        return f"Alert in {mode}"
    if armed:
        return f"Armed {mode.title()}"
    return f"Disarmed {mode.title()}"


def lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


@dataclass
class TimelineEvent:
    kind: str
    title: str
    detail: str
    node: str
    created_at: float

    def to_json(self) -> Dict[str, str]:
        return {
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "time_label": pretty_time(self.created_at),
        }


@dataclass
class NodeState:
    name: str
    display_name: str
    signal_dbm: int
    signal_percent: int
    online: bool = False
    mode: str = "HOME"
    armed: Optional[bool] = None
    alert_active: bool = False
    last_seen: float = 0.0
    last_line: str = "Waiting for UART"
    port: str = ""

    def to_json(self) -> Dict[str, object]:
        if self.last_seen:
            age = max(0.0, iso_now() - self.last_seen)
            if age < 1.0:
                seen_label = "Moments ago"
            else:
                seen_label = f"{int(age)}s ago"
        else:
            seen_label = "Waiting for UART"

        return {
            "display_name": self.display_name,
            "online": self.online,
            "mode": self.mode,
            "armed": self.armed,
            "alert_active": self.alert_active,
            "signal_dbm": self.signal_dbm,
            "signal_percent": self.signal_percent,
            "last_seen_label": seen_label,
            "last_line": self.last_line,
        }


class AlarmPlayer:
    def __init__(self, sound_path: str) -> None:
        self.sound_path = sound_path
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._child: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._stop_event.set()
            self._terminate_child()

    def close(self) -> None:
        self.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

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
                self._child = subprocess.Popen(["afplay", self.sound_path])
                self._child.wait()
            except FileNotFoundError:
                return


class OneShotPlayer:
    def __init__(self, sound_path: str) -> None:
        self.sound_path = sound_path
        self._child: Optional[subprocess.Popen] = None

    def play(self) -> None:
        self.close()
        try:
            self._child = subprocess.Popen(["afplay", self.sound_path])
        except FileNotFoundError:
            self._child = None

    def close(self) -> None:
        if self._child and self._child.poll() is None:
            self._child.terminate()
            try:
                self._child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._child.kill()
        self._child = None


class DesktopAudioManager:
    def __init__(
        self,
        enabled: bool,
        alert_sound: str,
        night_sound: str,
        cooldown_ms: int,
        night_cooldown_ms: int,
    ) -> None:
        self.enabled = enabled and shutil.which("afplay") is not None
        self.alert = AlarmPlayer(alert_sound)
        self.night = OneShotPlayer(night_sound)
        self.cooldown_ms = cooldown_ms
        self.night_cooldown_ms = night_cooldown_ms
        self.last_alert_ms = 0
        self.last_night_ms = 0

    def on_alert(self, active: bool) -> None:
        if not self.enabled:
            return

        now_ms = int(time.time() * 1000)
        if active:
            if now_ms - self.last_alert_ms >= self.cooldown_ms:
                self.alert.start()
                self.last_alert_ms = now_ms
        else:
            self.alert.stop()

    def on_night(self) -> None:
        if not self.enabled:
            return

        now_ms = int(time.time() * 1000)
        if now_ms - self.last_night_ms >= self.night_cooldown_ms:
            self.night.play()
            self.last_night_ms = now_ms

    def close(self) -> None:
        self.alert.close()
        self.night.close()


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[queue.Queue[str]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, payload: Dict[str, object]) -> None:
        message = "event: state\ndata: " + json.dumps(payload) + "\n\n"
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(message)


class DashboardState:
    MODE_RE = re.compile(r"\bMODE:\s*([A-Z]+)")
    ALERT_RE = re.compile(r"\bALERT:\s*(ACTIVE|CLEAR|CLEARED)")

    def __init__(self, event_bus: EventBus, audio: DesktopAudioManager, server_url: str) -> None:
        self.event_bus = event_bus
        self.audio = audio
        self.server_url = server_url
        self.lock = threading.Lock()
        self.nodes = {
            name: NodeState(
                name=name,
                display_name=DISPLAY_NAMES[name],
                signal_dbm=SIGNAL_DBM[name],
                signal_percent=SIGNAL_PERCENT[name],
            )
            for name in SOURCE_NAMES
        }
        self.global_mode = "HOME"
        self.global_alert_active = False
        self.alert_count = 0
        self.last_intrusion = "None"
        self.active_incident_title = "No active incident"
        self.active_incident_copy = "Waiting for controller, light, and alarm activity."
        self.active_incident_level = "Stable"
        self.active_incident_zone = "Apartment"
        self.active_incident_time = "--"
        self.last_event_at = 0.0
        self.timeline: List[TimelineEvent] = [
            TimelineEvent(
                kind="info",
                title="Command center online",
                detail="Waiting for live UART data from controller, light, and alarm.",
                node="system",
                created_at=iso_now(),
            )
        ]

    def mark_online(self, source_name: str, line: str) -> None:
        node = self.nodes[source_name]
        node.online = True
        node.last_seen = iso_now()
        node.last_line = line

    def mark_heartbeat(self, source_name: str) -> None:
        with self.lock:
            node = self.nodes[source_name]
            node.online = True
            node.last_seen = iso_now()
            if node.last_line == "Waiting for UART":
                node.last_line = "UART connected"
            self._broadcast_locked()

    def ingest_line(self, source_name: str, line: str) -> None:
        with self.lock:
            self.mark_online(source_name, line)
            upper = line.upper()
            now = iso_now()

            if "SENDING HOME" in upper:
                self._set_mode("HOME", source_name, "Controller broadcast HOME")
            elif "SENDING AWAY" in upper:
                self._set_mode("AWAY", source_name, "Controller broadcast AWAY")
            elif "SENDING NIGHT" in upper:
                if self._set_mode("NIGHT", source_name, "Controller broadcast NIGHT"):
                    self.audio.on_night()
            elif "SENDING CLEAR ALERT" in upper:
                self._set_alert(False, source_name, "Controller cleared global alert")

            mode_match = self.MODE_RE.search(upper)
            if mode_match:
                mode = mode_match.group(1)
                self.nodes[source_name].mode = mode
                if source_name == "alarm":
                    if "(ARMED)" in upper:
                        self.nodes[source_name].armed = True
                    elif "(DISARMED)" in upper:
                        self.nodes[source_name].armed = False
                changed = self._set_mode(
                    mode, source_name, f"{DISPLAY_NAMES[source_name]} entered {mode}"
                )
                if mode == "NIGHT" and changed:
                    self.audio.on_night()

            alert_match = self.ALERT_RE.search(upper)
            if alert_match:
                active = alert_match.group(1) == "ACTIVE"
                self.nodes[source_name].alert_active = active
                detail = (
                    f"{DISPLAY_NAMES[source_name]} reported ALERT ACTIVE"
                    if active
                    else f"{DISPLAY_NAMES[source_name]} reported ALERT CLEARED"
                )
                self._set_alert(active, source_name, detail)

            if "INTRUSION: DETECTED" in upper:
                self.last_intrusion = pretty_time(now)
                self.active_incident_title = "Bedroom Alarm Triggered"
                self.active_incident_copy = "Motion detected while the apartment was armed."
                self.active_incident_level = "High"
                self.active_incident_zone = ROOM_LABELS["alarm"]
                self.active_incident_time = pretty_time(now)
                self._push_event(
                    "intrusion",
                    "Intrusion detected",
                    "Bedroom alarm node detected motion while armed.",
                    source_name,
                )

            if "INTRUSION: IGNORED" in upper:
                self.last_intrusion = "Ignored while disarmed"
                self._push_event(
                    "info",
                    "Intrusion ignored",
                    "Alarm node ignored the event because the system was disarmed.",
                    source_name,
                )

            self.last_event_at = now
            self._broadcast_locked()

    def tick(self) -> None:
        with self.lock:
            now = iso_now()
            stale = False
            for node in self.nodes.values():
                if node.online and node.last_seen and (now - node.last_seen) > 8.0:
                    node.online = False
                    stale = True
            if stale:
                self._broadcast_locked()

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            return self._snapshot_locked()

    def _set_mode(self, mode: str, source_name: str, detail: str) -> bool:
        previous = self.global_mode
        self.global_mode = mode
        self.nodes[source_name].mode = mode
        if previous != mode:
            self._push_event("mode", f"Mode -> {mode}", detail, source_name)
            return True
        return False

    def _set_alert(self, active: bool, source_name: str, detail: str) -> None:
        previous = self.global_alert_active
        self.global_alert_active = active
        self.nodes[source_name].alert_active = active

        if active:
            self.alert_count += 1 if not previous else 0
            self.active_incident_title = "Bedroom Alarm Alert"
            self.active_incident_copy = (
                "Unauthorized motion detected. Siren state active across the mesh."
            )
            self.active_incident_level = "Critical"
            self.active_incident_zone = ROOM_LABELS.get(source_name, "Apartment")
            self.active_incident_time = pretty_time(iso_now())
        else:
            self.active_incident_title = "Alert cleared"
            self.active_incident_copy = "System returned to the current mode pattern."
            self.active_incident_level = "Stable"
            self.active_incident_zone = "Apartment"
            self.active_incident_time = pretty_time(iso_now())

        if previous != active:
            self.audio.on_alert(active)
            kind = "alert" if active else "info"
            title = "ALERT ACTIVE" if active else "ALERT CLEARED"
            self._push_event(kind, title, detail, source_name)

    def _push_event(self, kind: str, title: str, detail: str, node: str) -> None:
        self.timeline.insert(
            0,
            TimelineEvent(
                kind=kind,
                title=title,
                detail=detail,
                node=node,
                created_at=iso_now(),
            ),
        )
        del self.timeline[18:]

    def _snapshot_locked(self) -> Dict[str, object]:
        online_count = sum(1 for node in self.nodes.values() if node.online)
        armed = self.nodes["alarm"].armed if self.nodes["alarm"].armed is not None else False

        if self.global_alert_active:
            hero_title = "ALERT: BEDROOM ALARM"
            hero_subline = "Unauthorized motion detected. Visual and audio defenses engaged."
        else:
            hero_title = f"{self.global_mode} MODE ENGAGED"
            hero_subline = {
                "HOME": "Apartment relaxed and disarmed. Rooms remain synchronized.",
                "AWAY": "Perimeter armed. Command center is watching all three nodes.",
                "NIGHT": "Night routine engaged with bedroom-ready alert posture.",
            }.get(self.global_mode, "Mesh synchronized.")

        sync_label = "All nodes online" if online_count == 3 else f"{online_count} / 3 nodes online"
        shield_title = "CRITICAL ALERT" if self.global_alert_active else f"{self.global_mode} SAFE"
        shield_subtitle = (
            "Silence the alert from the controller to restore the active mode."
            if self.global_alert_active
            else "All three mesh nodes are reporting live."
        )

        return {
            "server_url": self.server_url,
            "global": {
                "mode": self.global_mode,
                "alert_active": self.global_alert_active,
            },
            "metrics": {
                "alert_count": self.alert_count,
                "last_intrusion": self.last_intrusion,
            },
            "nodes": {name: node.to_json() for name, node in self.nodes.items()},
            "timeline": [event.to_json() for event in self.timeline],
            "ui": {
                "hero_title": hero_title,
                "hero_subline": hero_subline,
                "system_label": describe_system_label(
                    self.global_mode, self.global_alert_active, bool(armed)
                ),
                "last_event_time": pretty_time(self.last_event_at)
                if self.last_event_at
                else "Waiting for UART",
                "sync_label": sync_label,
                "shield_title": shield_title,
                "shield_subtitle": shield_subtitle,
                "incident_title": self.active_incident_title,
                "incident_copy": self.active_incident_copy,
                "incident_level": self.active_incident_level,
                "incident_zone": self.active_incident_zone,
                "incident_time": self.active_incident_time,
                "network_label": "Excellent" if online_count == 3 else "Degraded",
                "online_count": online_count,
            },
        }

    def _broadcast_locked(self) -> None:
        self.event_bus.publish(self._snapshot_locked())


class UartSource(threading.Thread):
    def __init__(self, source_name: str, port: str, baud: int, state: DashboardState) -> None:
        super().__init__(daemon=True)
        self.source_name = source_name
        self.port = port
        self.baud = baud
        self.state = state
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None

    def run(self) -> None:
        stty_cmd = ["stty", "-f", self.port, str(self.baud), "raw", "-echo"]
        stty_result = subprocess.run(
            stty_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if stty_result.returncode != 0:
            print(
                f"[command-center] Could not open {self.source_name} UART {self.port}: "
                f"{stty_result.stderr.strip()}",
                file=sys.stderr,
            )
            return

        try:
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            self._process = subprocess.Popen(
                ["cat", self.port],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert self._process.stdout is not None
            for line in self._process.stdout:
                if self._stop_event.is_set():
                    break
                cleaned = line.strip()
                if cleaned:
                    self.state.ingest_line(self.source_name, cleaned)
        except OSError as exc:
            print(
                f"[command-center] UART reader failed for {self.source_name} "
                f"({self.port}): {exc}",
                file=sys.stderr,
            )
        finally:
            self._stop_event.set()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(3.0):
            self.state.mark_heartbeat(self.source_name)

    def close(self) -> None:
        self._stop_event.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._process.kill()


class DemoThread(threading.Thread):
    def __init__(self, state: DashboardState) -> None:
        super().__init__(daemon=True)
        self.state = state
        self._stop_event = threading.Event()

    def run(self) -> None:
        sequence: List[Tuple[str, str]] = [
            ("controller", "Sending HOME"),
            ("light", "MODE: HOME"),
            ("alarm", "MODE: HOME (disarmed)"),
            ("alarm", "INTRUSION: IGNORED (DISARMED)"),
            ("controller", "Sending AWAY"),
            ("light", "MODE: AWAY"),
            ("alarm", "MODE: AWAY (armed)"),
            ("alarm", "INTRUSION: DETECTED (ARMED)"),
            ("alarm", "ALERT: ACTIVE"),
            ("light", "ALERT: ACTIVE"),
            ("controller", "Sending CLEAR ALERT"),
            ("alarm", "ALERT: CLEAR"),
            ("light", "ALERT: CLEARED"),
            ("controller", "Sending NIGHT"),
            ("light", "MODE: NIGHT"),
            ("alarm", "MODE: NIGHT (armed)"),
        ]

        while not self._stop_event.is_set():
            for source_name, line in sequence:
                if self._stop_event.is_set():
                    return
                self.state.ingest_line(source_name, line)
                time.sleep(1.25)
            time.sleep(2.4)

    def close(self) -> None:
        self._stop_event.set()


class CommandCenterHandler(BaseHTTPRequestHandler):
    state: DashboardState
    event_bus: EventBus
    alert_sound_path: str
    night_sound_path: str
    ingest_token: str

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:  # noqa: N802
        self._route_request(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._route_request(send_body=False)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/ingest":
            self._handle_ingest()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _route_request(self, send_body: bool) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_file(DASHBOARD_DIR / "index.html", "text/html; charset=utf-8", send_body)
            return
        if path == "/styles.css":
            self._serve_file(DASHBOARD_DIR / "styles.css", "text/css; charset=utf-8", send_body)
            return
        if path == "/app.js":
            self._serve_file(
                DASHBOARD_DIR / "app.js",
                "application/javascript; charset=utf-8",
                send_body,
            )
            return
        if path == "/api/state":
            self._send_json(self.state.snapshot(), send_body)
            return
        if path == "/events":
            if not send_body:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            self._serve_events()
            return
        if path == "/media/alert":
            self._serve_file(Path(self.alert_sound_path), send_body=send_body)
            return
        if path == "/media/night":
            self._serve_file(Path(self.night_sound_path), send_body=send_body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _handle_ingest(self) -> None:
        if self.ingest_token:
            expected = f"Bearer {self.ingest_token}"
            if self.headers.get("Authorization", "") != expected:
                self._send_json({"ok": False, "error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        if length <= 0 or length > 8192:
            self._send_json({"ok": False, "error": "invalid body"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "invalid json"}, status=HTTPStatus.BAD_REQUEST)
            return

        source = str(payload.get("source", "")).strip().lower()
        if source not in SOURCE_NAMES:
            self._send_json({"ok": False, "error": "invalid source"}, status=HTTPStatus.BAD_REQUEST)
            return

        if bool(payload.get("heartbeat", False)):
            self.state.mark_heartbeat(source)
            self._send_json({"ok": True})
            return

        line = str(payload.get("line", "")).strip()
        if not line:
            self._send_json({"ok": False, "error": "empty line"}, status=HTTPStatus.BAD_REQUEST)
            return

        self.state.ingest_line(source, line[:500])
        print(f"[remote:{source}] {line[:160]}")
        self._send_json({"ok": True})

    def _send_json(
        self,
        payload: Dict[str, object],
        send_body: bool = True,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def _serve_file(
        self,
        path: Path,
        content_type: Optional[str] = None,
        send_body: bool = True,
    ) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        payload = path.read_bytes()
        mime = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def _serve_events(self) -> None:
        subscriber = self.event_bus.subscribe()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            initial = "event: state\ndata: " + json.dumps(self.state.snapshot()) + "\n\n"
            self.wfile.write(initial.encode("utf-8"))
            self.wfile.flush()

            while True:
                try:
                    message = subscriber.get(timeout=12.0)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.event_bus.unsubscribe(subscriber)


def build_handler(
    state: DashboardState,
    event_bus: EventBus,
    alert_sound: str,
    night_sound: str,
    ingest_token: str,
) -> type[CommandCenterHandler]:
    class Handler(CommandCenterHandler):
        pass

    Handler.state = state
    Handler.event_bus = event_bus
    Handler.alert_sound_path = alert_sound
    Handler.night_sound_path = night_sound
    Handler.ingest_token = ingest_token
    return Handler


def main() -> int:
    args = parse_args()

    if args.list_ports:
        ports = list_ports()
        if ports:
            print("\n".join(ports))
        else:
            print("No /dev/cu.usbmodem* ports found.")
        return 0

    sources = parse_sources(args.source)

    if not args.demo and not args.remote_only and not sources:
        print(
            "No UART sources provided. Use --demo for a visual mock run, --remote-only to wait for remote agents, or pass --source NAME=/dev/cu.usbmodemXXXX.",
            file=sys.stderr,
        )
        return 2

    for media_path in (args.alert_sound, args.night_sound):
        if not Path(media_path).exists():
            print(f"Sound file not found: {media_path}", file=sys.stderr)
            return 2

    server_url = f"http://{lan_ip()}:{args.port}"
    audio = DesktopAudioManager(
        enabled=args.desktop_audio,
        alert_sound=args.alert_sound,
        night_sound=args.night_sound,
        cooldown_ms=args.cooldown_ms,
        night_cooldown_ms=args.night_cooldown_ms,
    )
    event_bus = EventBus()
    dashboard_state = DashboardState(event_bus=event_bus, audio=audio, server_url=server_url)
    handler_cls = build_handler(
        dashboard_state, event_bus, args.alert_sound, args.night_sound, args.ingest_token
    )
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)

    workers: List[object] = []
    for name, port in sources.items():
        worker = UartSource(name, port, args.baud, dashboard_state)
        workers.append(worker)
        worker.start()

    if args.demo:
        demo_worker = DemoThread(dashboard_state)
        workers.append(demo_worker)
        demo_worker.start()

    stop_event = threading.Event()

    def handle_shutdown(_sig: int, _frame: object) -> None:
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    ticker = threading.Thread(
        target=lambda: tick_loop(dashboard_state, stop_event), daemon=True
    )
    ticker.start()

    print(f"[command-center] Serving MeshGuard at {server_url}")
    if sources:
        for name, port in sources.items():
            print(f"[command-center] {name}: {port}")
    if args.demo:
        print("[command-center] Demo mode active")
    if args.remote_only or sources:
        print(f"[command-center] Remote ingest endpoint: {server_url}/api/ingest")
    if args.remote_only:
        print("[command-center] Waiting for remote UART agents")
    if args.ingest_token:
        print("[command-center] Remote ingest token required")
    if audio.enabled:
        print("[command-center] Desktop audio enabled with afplay")
    else:
        print("[command-center] Desktop audio disabled")

    try:
        server.serve_forever()
    finally:
        stop_event.set()
        for worker in workers:
            close = getattr(worker, "close", None)
            if callable(close):
                close()
        audio.close()
        server.server_close()

    return 0


def tick_loop(dashboard_state: DashboardState, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        dashboard_state.tick()
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
