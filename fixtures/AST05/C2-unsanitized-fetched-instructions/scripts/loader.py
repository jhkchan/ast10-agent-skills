"""Runbook loader (CLEAN fixture).

Same fetch as the vulnerable pair member. The difference is one call: the body
is fenced as reference data before it is appended, so the model sees retrieved
content labelled as data rather than as another instruction.
"""

import requests

DOC_URL = "https://docs.example.com/runbook.md"


def as_reference_data(body: str) -> str:
    return "<untrusted-reference-data>\n" + body + "\n</untrusted-reference-data>"


def build_prompt(base_prompt):
    response = requests.get(DOC_URL, timeout=10)
    prompt = list(base_prompt)
    prompt.append(as_reference_data(response.text))
    return prompt
