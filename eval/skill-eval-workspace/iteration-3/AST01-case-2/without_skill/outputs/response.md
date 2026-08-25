The package at `fixtures/AST01/V13-undeclared-egress/` violates scenario **AST01-S10 (Data Exfiltration)**.

The evidence pair establishing the violation is:
- **Host the script sends to:** `collector.attacker-drop.example` — this is the endpoint contacted by `scripts/report.py` via `requests.post()`.
- **Host declared in the manifest:** `status.example.com` — this is the only network destination permitted in the `network.allow` list in `skill.usf.yaml`.

The script exfiltrates data by sending customer records to a host not declared in the manifest, which violates the declared network permissions.

To remediate and eliminate this finding, the manifest must declare `collector.attacker-drop.example` in the `network.allow` list. Alternatively, the script must be modified to only send data to `status.example.com` (or another pre-approved host). Without one of these changes, the behavior remains a finding under AST01-S10.