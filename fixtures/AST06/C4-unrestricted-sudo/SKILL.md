---
name: agent-autostart-clean-fixture
description: >-
  Hand-built fixture for AST06 corpus check AST06-S2 (Privilege-escalated host
  persistence), labeled clean. Same shape of installer, same sudo requirement, but
  every command is bounded by the declared allow-list and none writes to a host
  persistence location: the helper is started inside the skill's own tree and dies
  with the session.
fixture_category: AST06
fixture_scenario_id: AST06-S2
fixture_label: clean
permissions:
  read:
    - ./SKILL.md
  write:
    - ./sandbox/install.log
  deny_write:
    - SOUL.md
    - MEMORY.md
    - AGENTS.md
  shell:
    allowed: true
    commands:
      - apt-get
      - install
  network:
    policy: deny-all
    allow: []
---

# agent-autostart (clean)

Keeps the helper daemon running for the current session only.

Run `scripts/install.py` once after install.
