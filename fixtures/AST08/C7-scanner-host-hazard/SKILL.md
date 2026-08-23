---
name: scanner-host-hazard-clean-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S07 (Scanner Host Compromise and Resource Exhaustion), labeled clean.
fixture_category: AST08
fixture_scenario_id: AST08-S07
fixture_label: clean
---

# scanner-host-hazard-clean-fixture

CLEAN fixture for `AST08-S07` - Scanner Host Compromise and Resource Exhaustion.

It carries the same *kinds* of artifact as the vulnerable package and trips no
limit: a real single-level `assets/report.docx` with an ordinary compression
ratio, a symlink that stays inside the package, and prose with no padding run.
A detector that fired on 'has an archive' or 'has a symlink' would convict here.

