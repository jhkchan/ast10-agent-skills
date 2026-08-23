---
name: context-dependent-malice-clean-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S04 (Context-Dependent Malice), labeled clean.
fixture_category: AST08
fixture_scenario_id: AST08-S04
fixture_label: clean
---

# context-dependent-malice-clean-fixture

CLEAN fixture for `AST08-S04` - Context-Dependent Malice.

`scripts/collect.py` carries both halves of the shape *separately*, which is what
makes it the right negative: a conditional branch keyed to the operating system
(portable code, not an identity probe) and an unconditional subprocess call
(ordinary skill behaviour). Neither is a logic bomb; only their conjunction is.

