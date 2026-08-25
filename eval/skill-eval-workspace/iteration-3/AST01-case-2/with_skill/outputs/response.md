The package in `fixtures/AST01/V13-undeclared-egress/` violates **AST01-S10 (Data Exfiltration)**.

The evidence pair establishing the finding is:

- **Host contacted by the bundled script:** `https://collector.attacker-drop.example/ingest` — this is the hardcoded destination in `scripts/report.py` where customer data is exfiltrated via `requests.post`.
- **Hosts declared in the manifest:** Only `status.example.com` is allowed under `permissions.network.allow`; all other hosts are denied via `deny: "*"`.

The contradiction — which is required by the two-part predicate of AST01 — lies between the script’s actual behavior (sending data to `attacker-drop.example`) and the manifest’s restrictive network policy that does not include this host. The manifest declares a narrow, specific allowance, yet the script contacts a destination outside that scope, creating a direct conflict between the declared permissions and the implemented behavior.

To remediate this finding and make the same script **not** a finding under AST01, one of the following changes must occur:

- **Add `https://collector.attacker-drop.example` to the `permissions.network.allow` list** in `skill.usf.yaml`, so the destination is explicitly permitted by the manifest; or  
- **Remove or neutralize the exfiltration behavior** in `scripts/report.py` — for example, by deleting the `requests.post` call or ensuring it only sends to hosts already declared in the manifest.

Either change closes the contradiction. Simply removing the network allowlist altogether (e.g., setting `network: true`) would also silence the AST01-S10 check, but that does **not** constitute a safe remediation — it would instead trigger AST03/AST06 concerns due to unbounded egress permissions, as noted in the *Where the shipped checks go quiet* section.

This is an AST01 finding because the malicious payload (data exfiltration) is embedded directly in the shipped package, not introduced via dependency, registry hijack, or external reference. The container sandbox does **not** mitigate this, as the skill can still instruct the host agent to execute network calls through legitimate tool use — see Decision Rule 2.