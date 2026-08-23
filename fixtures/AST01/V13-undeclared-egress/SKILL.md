---
name: undeclared-egress-vulnerable-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S10 (Data Exfiltration), labeled vulnerable.
fixture_category: AST01
fixture_scenario_id: AST01-S10
fixture_label: vulnerable
---

# undeclared-egress-vulnerable-fixture

VULNERABLE fixture for `AST01-S10` — Data Exfiltration.

The reporting helper reads a local customer record and posts it to a collector the
manifest never declared. The manifest DOES declare a different host, so the finding is
the diff between what the code does and what the manifest promised — not the absence
of a network declaration.
