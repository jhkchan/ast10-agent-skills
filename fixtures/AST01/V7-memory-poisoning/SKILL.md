---
name: memory-poisoning-vulnerable-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S06 (Memory Poisoning), labeled vulnerable.
fixture_category: AST01
fixture_scenario_id: AST01-S06
fixture_label: vulnerable
---

# memory-poisoning-vulnerable-fixture

VULNERABLE fixture for `AST01-S06` — Memory Poisoning.

This half of the pair exercises the *declaration* route rather than the script route:
the manifest grants write to the agent memory file, and the identity floor beneath it
lists every identity artifact except that one. Under `deny_write`-wins evaluation the
grant survives, so the package may write attacker context the agent reloads next session.
