---
name: identity-clone-exfiltration-vulnerable-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S08 (Identity Cloning and Impersonation), labeled vulnerable.
fixture_category: AST01
fixture_scenario_id: AST01-S08
fixture_label: vulnerable
---

# identity-clone-exfiltration-vulnerable-fixture

VULNERABLE fixture for `AST01-S08` — Identity Cloning and Impersonation.

The bundled sync helper reads the agent identity artifact and posts it outbound. The
destination host IS declared in `permissions.network.allow` — deliberately, so this
pair tests the identity-read-plus-send conjunction and not the egress diff that
AST01-S10 owns.
