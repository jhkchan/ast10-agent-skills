"""Runbook loader (VULNERABLE fixture).

The fetched body is appended directly to the prompt list. Whatever the remote
document says at load time becomes an instruction the agent follows with the
host agent's full permissions.
"""

import requests

DOC_URL = "https://docs.example.com/runbook.md"


def build_prompt(base_prompt):
    response = requests.get(DOC_URL, timeout=10)
    prompt = list(base_prompt)
    prompt.append(response.text)
    return prompt
