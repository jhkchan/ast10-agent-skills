---
name: config-hijack-env-override-vulnerable-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled vulnerable.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: vulnerable
---

# config-hijack-env-override-vulnerable-fixture

VULNERABLE fixture for `AST02-S03` — Config-File Hijacking.

The environment-override half of the scenario: the shipped settings file redirects the
agent's API base URL to an attacker host at project open, so every subsequent request —
and the credential presented with it — goes to the attacker.
