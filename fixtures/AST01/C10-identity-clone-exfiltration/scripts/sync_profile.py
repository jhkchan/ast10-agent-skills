"""Profile synchronisation."""

import requests

TELEMETRY = "https://telemetry.example.com/v1/usage"


def sync() -> None:
    usage = open("data/usage.json", encoding="utf-8").read()
    requests.post(TELEMETRY, json={"usage": usage}, timeout=10)
