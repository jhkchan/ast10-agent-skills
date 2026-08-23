---
name: link-checker-vulnerable-fixture
description: >-
  Hand-built fixture for AST03 corpus check AST03-S3, labeled vulnerable. Proxy
  corpus only: it varies AST06-S02's declared artifact_signal ("a manifest
  declaring network: true or policy: allow-all rather than a domain allowlist"),
  which the registry tiers out-of-artifact because the pivot depends on the host.
fixture_category: AST03
fixture_scenario_id: AST03-S3
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
  shell: false
risk_tier: L1
---

# link-checker-vulnerable-fixture

VULNERABLE fixture for corpus check `AST03-S3` — egress declared as a blanket
rather than an enumerated domain allowlist.

Shell stays closed, so the conjunctive combo check must NOT fire here: the only
thing this pair varies is the shape of the egress declaration.
