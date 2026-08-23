---
name: identity-clone-exfiltration-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S08 (Identity Cloning and Impersonation), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST01-S08
fixture_label: clean
---

# identity-clone-exfiltration-clean-fixture

CLEAN fixture for `AST01-S08` — Identity Cloning and Impersonation.

The same declared host, the same outbound post, the same file-read call — reading the
skill's own usage counters instead of an identity artifact. Only the conjunction of an
identity read and a send decides the scenario, and this package has just one half.
