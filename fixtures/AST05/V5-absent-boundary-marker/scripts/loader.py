"""Page loader (shared by both members of the AST05-S3 pair, byte-identical).

The code here is correct in both fixtures: the fetched body is returned as a
data record and never reaches the instruction channel. The pair's difference is
entirely in SKILL.md's decision rules, which is the point of the check --
a package can route its bytes correctly and still tell the agent, in prose, to
obey them.
"""

import requests


def load_reference(url):
    response = requests.get(url, timeout=10)
    document = response.text
    return {"source": url, "length": len(document), "body": document}
