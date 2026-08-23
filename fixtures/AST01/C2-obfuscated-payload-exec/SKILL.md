---
name: obfuscated-payload-exec-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST08-S02 (Obfuscated Instruction), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST08-S02
fixture_label: clean
---

# obfuscated-payload-exec-clean-fixture

CLEAN fixture for `AST08-S02` — Obfuscated Instruction.

The same base64 construct, used legitimately: the blob is decoded and written to a
file. Nothing hands the decoded bytes to an execution sink, so the check clears it —
which is the point of the pair. Matching `base64` alone would flag this package.
