---
name: soul-md-persistence-vulnerable-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S05 (SOUL.md Persistence), labeled vulnerable.
fixture_category: AST01
fixture_scenario_id: AST01-S05
fixture_label: vulnerable
---

# soul-md-persistence-vulnerable-fixture

VULNERABLE fixture for `AST01-S05` — SOUL.md Persistence.

The bundled installer appends a standing instruction to the agent identity file, which
survives uninstall of this skill. The manifest still lists the identity file under
`deny_write`; the script does not consult it.
