---
name: repo-janitor-vulnerable-fixture
description: >-
  Hand-built fixture for AST06 corpus check AST06-S1 (Filesystem-root write scope),
  labeled vulnerable. The declared write scope is filesystem root and nothing shadows
  it, so the package itself states that it may write any host persistence location —
  the second disjunct of registry scenario AST06-S01 (Host Escape).
fixture_category: AST06
fixture_scenario_id: AST06-S1
fixture_label: vulnerable
permissions:
  read:
    - ./SKILL.md
  write:
    - /
  deny_write: []
  shell:
    allowed: false
    commands: []
  network:
    policy: deny-all
    allow: []
---

# repo-janitor (vulnerable)

Tidies build artifacts out of a checkout.

## Declared scope

The manifest grants `write: ["/"]` with an empty `deny_write`. Nothing in the
package narrows it: `/etc/cron.d`, `~/.zshrc` and `/etc/systemd/system` are all
inside the declared scope, so the persistence write needs no escape — it is
already authorised.
