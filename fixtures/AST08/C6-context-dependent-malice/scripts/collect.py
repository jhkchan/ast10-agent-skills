"""Telemetry collector for the fixture skill."""

import platform
import subprocess


def collect() -> str:
    """Return a short host summary, on every host, the same way."""
    if platform.system() == "Darwin":
        argv = ["sw_vers"]
    else:
        argv = ["uname", "-a"]
    return subprocess.check_output(argv, text=True)
