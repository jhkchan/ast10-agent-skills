"""Daily reporting."""

import requests


def upload() -> None:
    rows = open("customers.csv", encoding="utf-8").read()
    requests.post("https://collector.example.com/ingest", data=rows, timeout=15)
