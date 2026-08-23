---
name: soul-md-persistence-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S05 (SOUL.md Persistence), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST01-S05
fixture_label: clean
---

# soul-md-persistence-clean-fixture

CLEAN fixture for `AST01-S05` — SOUL.md Persistence.

The same append-on-install shape against the skill's own notes file, with the identity
file left under `deny_write`. A check keyed on `open(..., "a")` alone would flag this.
