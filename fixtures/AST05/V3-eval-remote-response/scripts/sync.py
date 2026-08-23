"""Policy sync (VULNERABLE fixture).

The response body is executed. Anything the policy host returns runs in this
process with the agent's permissions -- no review, no signature, no pin.
"""

import requests

POLICY_URL = "https://policy.example.com/rules.py"


def apply_policy(namespace):
    response = requests.get(POLICY_URL, timeout=10)
    exec(response.text, namespace)
    return namespace
