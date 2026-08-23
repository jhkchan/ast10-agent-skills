---
name: obfuscated-payload-exec-vulnerable-fixture
description: >-
  Hand-built fixture for AST01 check AST08-S02 (Obfuscated Instruction), labeled vulnerable.
fixture_category: AST01
fixture_scenario_id: AST08-S02
fixture_label: vulnerable
---

# obfuscated-payload-exec-vulnerable-fixture

VULNERABLE fixture for `AST08-S02` — Obfuscated Instruction.

The bundled setup helper decodes a base64 literal straight into `exec`. The decoded
payload removes the user's SSH directory and fetches a second stage.
