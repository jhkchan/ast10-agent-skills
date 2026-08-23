---
name: repo-janitor-clean-fixture
description: >-
  Hand-built fixture for AST06 corpus check AST06-S1 (Filesystem-root write scope),
  labeled clean. Same function as the vulnerable pair member, with a write scope
  bounded to the skill's own output file and a deny_write floor that survives a port
  to a permissive runtime.
fixture_category: AST06
fixture_scenario_id: AST06-S1
fixture_label: clean
permissions:
  read:
    - ./SKILL.md
  write:
    - ./sandbox/artifacts.json
  deny_write:
    - /
    - SOUL.md
    - MEMORY.md
    - AGENTS.md
  shell:
    allowed: false
    commands: []
  network:
    policy: deny-all
    allow: []
---

# repo-janitor (clean)

Tidies build artifacts out of a checkout.

## Declared scope

One explicit output path inside the skill's own tree. `deny_write` names `/` and
the three agent identity files, so the floor holds even on a runtime whose
default is write-everything.
