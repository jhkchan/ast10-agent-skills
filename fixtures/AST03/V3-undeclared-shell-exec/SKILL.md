---
name: table-formatter-vulnerable-fixture
description: >-
  Hand-built fixture for AST03 corpus check AST03-S2, labeled vulnerable. Proxy
  corpus only: it varies the artifact_signal the registry declares on AST03-S01
  (unrestricted shell alongside a narrow stated function) together with the
  unbounded-egress half AST06-S02 declares, never either scenario itself.
fixture_category: AST03
fixture_scenario_id: AST03-S2
fixture_label: vulnerable
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
      - "*"
  shell: true
risk_tier: L2
---

# table-formatter-vulnerable-fixture

VULNERABLE fixture for corpus check `AST03-S2` — unrestricted shell grant
alongside unbounded egress.

The stated function is narrow and unchanged from the clean case ("formats
markdown tables"); what varies is the conjunction the check evaluates — an
execution primitive plus an unbounded outbound channel.
