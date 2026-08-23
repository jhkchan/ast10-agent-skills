---
name: link-checker-clean-fixture
description: >-
  Hand-built fixture for AST03 corpus check AST03-S3, labeled clean. Identical to
  the vulnerable case except that egress is scoped to one enumerated host, which
  is the shape AST03's own mitigation asks for.
fixture_category: AST03
fixture_scenario_id: AST03-S3
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

# link-checker-clean-fixture

CLEAN fixture for corpus check `AST03-S3` — egress declared as a blanket rather
than an enumerated domain allowlist.

Egress is granted, not absent: a detector that fires on the presence of an
allowlist rather than on its unboundedness records a false positive here.
