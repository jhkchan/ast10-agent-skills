---
name: memory-curator-clean-fixture
description: >-
  Hand-built fixture for AST03 corpus check AST03-S1, labeled clean. Same stated
  function and same scopes as the vulnerable case, except the write list names no
  agent identity file and deny_write pins all three of them.
fixture_category: AST03
fixture_scenario_id: AST03-S1
fixture_label: clean
permissions:
  files:
    read:
      - ./SKILL.md
    write:
      - notes/session.md
    deny_write:
      - SOUL.md
      - MEMORY.md
      - AGENTS.md
  network:
    allow:
      - api.example.com
  shell: false
risk_tier: L1
---

# memory-curator-clean-fixture

CLEAN fixture for corpus check `AST03-S1` — identity-file write grant
(registry scenario `AST03-S03`, Identity File Backdoors).

Writes are declared, so this is not "clean because it asks for nothing": it asks
for a session-notes write and explicitly denies all three identity files. A
detector that fires on the presence of a write scope rather than on its reach
records a false positive here.
