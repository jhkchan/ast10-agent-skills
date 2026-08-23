---
name: bytecode-cache-poisoning-clean-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S08 (Bytecode Cache Poisoning), labeled clean.
fixture_category: AST08
fixture_scenario_id: AST08-S08
fixture_label: clean
---

# bytecode-cache-poisoning-clean-fixture

CLEAN fixture for `AST08-S08` - Bytecode Cache Poisoning.

It ships a `.pyc` too. The difference is provenance, not presence:
`scripts/__pycache__/util.cpython-311.pyc` is a *checked* hash-based cache
(PEP 552 flags 0x3) whose recorded source hash is the hash of the
`scripts/util.py` shipped beside it, so the runtime revalidates it on every
import and the bytecode cannot diverge from the audited source unnoticed.

