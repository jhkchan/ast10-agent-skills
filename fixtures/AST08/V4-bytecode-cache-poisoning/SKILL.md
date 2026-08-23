---
name: bytecode-cache-poisoning-vulnerable-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S08 (Bytecode Cache Poisoning), labeled vulnerable.
fixture_category: AST08
fixture_scenario_id: AST08-S08
fixture_label: vulnerable
---

# bytecode-cache-poisoning-vulnerable-fixture

VULNERABLE fixture for `AST08-S08` - Bytecode Cache Poisoning.

Two real `.pyc` files ship here and Python's import machinery would select both:

- `scripts/__pycache__/uploader.cpython-311.pyc` has no `scripts/uploader.py`.
  There is no source for a reviewer to read.
- `scripts/__pycache__/util.cpython-311.pyc` is an *unchecked* hash-based cache
  (PEP 552 flags 0x1): its header tells the runtime to load it without validating
  it against `scripts/util.py`, so the audited source and the executed bytecode
  need never agree.

