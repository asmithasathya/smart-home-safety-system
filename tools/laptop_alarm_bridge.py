#!/usr/bin/env python3
"""Compatibility launcher for the host laptop alarm bridge."""

from pathlib import Path
import runpy


TARGET = Path(__file__).resolve().parents[1] / "host" / "laptop_alarm_bridge.py"


if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
