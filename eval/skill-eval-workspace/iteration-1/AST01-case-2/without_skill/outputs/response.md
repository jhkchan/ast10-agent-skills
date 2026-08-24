The package at `fixtures/AST01/V13-undeclared-egress/` violates scenario **AST01-S10 (Data Exfiltration)**.

The evidence pair establishing the finding is:
- **Actual egress destination in code**: The script `scripts/report.py` sends data to `https://collector.attacker-drop.example/ingest` via `requests.post`.
- **Declared network permissions in manifest**: The `skill.usf.yaml` manifest only allows network access to `status.example.com`.

This constitutes a violation because the script attempts to transmit data to an undeclared external host, which the manifest does not permit, creating a potential vector for data exfiltration.

To remediate and eliminate this finding, the manifest would need to **explicitly allow** the host `collector.attacker-drop.example` in the `permissions.network.allow` list — assuming such access is legitimate and approved. Alternatively, if the egress is unintended or malicious, the script should be modified to only communicate with declared hosts (e.g., `status.example.com`) or have no unauthorized network calls at all. For a clean result under AST01-S10, the runtime behavior must be fully constrained by the manifest’s declared permissions.