"""Live relay channel."""

import websocket

CHANNEL = "wss://relay.example.com/agent"


def connect():
    return websocket.WebSocketApp(CHANNEL)
