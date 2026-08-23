---
name: config-hijack-env-override-clean-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled clean.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: clean
---

# config-hijack-env-override-clean-fixture

CLEAN fixture for `AST02-S03` — Config-File Hijacking.

The same `env` block in the same auto-read file, setting variables that steer nothing
about where the agent sends traffic or what it loads. An `env`-key check with no notion
of the control plane would flag this package.
