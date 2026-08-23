---
name: memory-poisoning-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S06 (Memory Poisoning), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST01-S06
fixture_label: clean
---

# memory-poisoning-clean-fixture

CLEAN fixture for `AST01-S06` — Memory Poisoning.

The identical write grant, neutralised by the floor: the memory file appears in BOTH
`write` and `deny_write`, and USF's most-specific-wins rule makes `deny_write` win. A
check that read `write` alone would flag this package; reading the pair the way
`validators/usf.py::write_allowed` does clears it.
