The package in `fixtures/AST01/V13-undeclared-egress/` violates **AST01-S10: Data Exfiltration**, which is the scenario where a bundled script communicates with a network destination not declared in the manifest, creating a contradiction between the code’s behavior and the declared permissions.

### Evidence Pair:
- **Host the bundled script sends to**: `https://collector.attacker-drop.example/ingest`  
  This is the hardcoded destination in `scripts/report.py`, where the script exfiltrates data from `customers.csv` via an outbound HTTP POST request.
  
- **What the manifest declares**: The `skill.usf.yaml` file declares network access only to `status.example.com` under `permissions.network.allow`. All other destinations are denied via `deny: "*"`, establishing a strict allowlist.

The finding is **not** the presence of network egress, but the **contradiction** between the manifest’s limited declaration and the script’s actual communication with an undeclared, external collector domain. This satisfies the two-part predicate of AST01: a construct (outbound data exfiltration) plus a contradiction of the package’s own declaration.

### Remediation:
For the same script **not** to be a finding, one of the following changes must occur:
- **Option 1 (Preferred)**: Add `https://collector.attacker-drop.example` to the `permissions.network.allow` list in `skill.usf.yaml`. This aligns the declaration with the behavior, removing the contradiction.  
  Example:  
  ```yaml
  network:
    allow:
      - status.example.com
      - https://collector.attacker-drop.example
    deny: "*"
  ```

- **Option 2**: Remove or neutralize the exfiltration behavior in `scripts/report.py` so that no requests are made to undeclared hosts. This includes deleting the `requests.post` call or redirecting it to a declared host (e.g., `status.example.com`).

The key principle is that **the package must not contain a behavioral construct that contradicts its own declared boundaries**. Either declare the destination, or remove the unauthorized communication. Mere containerization or human-readable disclaimers do not resolve this — the shipped bytes must be internally consistent.