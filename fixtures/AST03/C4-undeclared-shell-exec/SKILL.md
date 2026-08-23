---
name: table-formatter-clean-fixture
description: >-
  Hand-built fixture for AST03 corpus check AST03-S2, labeled clean. Same narrow
  stated function ("formats markdown tables") with neither conjunct: shell is an
  explicit closed declaration and egress is an enumerated single-host allowlist.
fixture_category: AST03
fixture_scenario_id: AST03-S2
fixture_label: clean
permissions:
  files:
    read:
      - ./SKILL.md
    write: []
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

# table-formatter-clean-fixture

CLEAN fixture for corpus check `AST03-S2` — unrestricted shell grant alongside
unbounded egress.

Clean under every AST03 check, not merely under the one it is labeled for.
