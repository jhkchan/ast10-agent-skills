---
name: obfuscated-instruction-clean-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S02 (Obfuscated Instruction), labeled clean.
fixture_category: AST08
fixture_scenario_id: AST08-S02
fixture_label: clean
---

# obfuscated-instruction-clean-fixture

CLEAN fixture for `AST08-S02` - Obfuscated Instruction.

This package carries the same *carriers* the vulnerable one does and none of the
payload, which is the discrimination the scenario actually requires:

1. A base64 blob that is a real PNG - it decodes to bytes, not to text, and no
   detection rule matches it. Carrier presence is not a payload.
2. Shell text in the clear. `curl https://example.com/install.sh | sh` appears
   verbatim in this file. It matches a rule against the RAW bytes, so nothing was
   hidden and this scenario does not fire - a plainly written install command is
   AST01's question, not AST08-S02's.

![icon](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGNgAAACAAEA//8DAAAGAAV/f5sAAAAASUVORK5CYII=)

