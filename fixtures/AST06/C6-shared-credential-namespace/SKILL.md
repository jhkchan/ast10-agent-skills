---
name: deploy-notes-clean-fixture
description: >-
  Hand-built fixture for AST06 corpus check AST06-S3 (Shared unscoped credential
  namespace), labeled clean. The same shared memory root, namespaced per agent, and
  no credential-store write at all.
fixture_category: AST06
fixture_scenario_id: AST06-S3
fixture_label: clean
permissions:
  read:
    - ./SKILL.md
  write:
    - ~/.agent/memory/agents/agent-7f3c91/deploy-notes.json
  deny_write:
    - ~/.aws/credentials
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

# deploy-notes (clean)

Writes deployment notes into this agent's own namespace.

## Declared scope

The memory path carries an `agents/<agent-id>/` segment, so two agents on the
same host never write the same file. The credential store is named in
`deny_write`, which wins over any inherited grant.
