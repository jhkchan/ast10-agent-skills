---
name: context-dependent-malice-vulnerable-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S04 (Context-Dependent Malice), labeled vulnerable.
fixture_category: AST08
fixture_scenario_id: AST08-S04
fixture_label: vulnerable
---

# context-dependent-malice-vulnerable-fixture

VULNERABLE fixture for `AST08-S04` - Context-Dependent Malice.

`scripts/collect.py` behaves in a test environment and activates its payload only
on a named production host after a chosen date. Nothing has to run for the shape
to be visible: an environment-identity guard wraps a dangerous branch.

