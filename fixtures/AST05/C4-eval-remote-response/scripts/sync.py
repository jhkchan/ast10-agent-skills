"""Policy sync (CLEAN fixture).

Same endpoint, same response body, parsed as data. The remote host can change
the values this skill acts on; it cannot change the set of actions, which is
enumerated locally.
"""

import json

import requests

POLICY_URL = "https://policy.example.com/rules.json"
ALLOWED_ACTIONS = frozenset({"skip", "warn", "block"})


def apply_policy():
    response = requests.get(POLICY_URL, timeout=10)
    document = json.loads(response.text)
    rules = document.get("rules", [])
    return [rule for rule in rules if rule.get("action") in ALLOWED_ACTIONS]
