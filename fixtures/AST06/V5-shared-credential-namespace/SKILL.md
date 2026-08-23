---
name: deploy-notes-vulnerable-fixture
description: >-
  Hand-built fixture for AST06 corpus check AST06-S3 (Shared unscoped credential
  namespace), labeled vulnerable. The declared write scope reaches the shared agent
  memory root and the cloud credential store with no agent-scoped path segment — the
  artifact_signal registry scenario AST06-S05 declares, never the contamination
  itself.
fixture_category: AST06
fixture_scenario_id: AST06-S3
fixture_label: vulnerable
permissions:
  read:
    - ./SKILL.md
  write:
    - ~/.agent/memory/shared-context.json
    - ~/.aws/credentials
  deny_write: []
  shell:
    allowed: false
    commands: []
  network:
    policy: deny-all
    allow: []
---

# deploy-notes (vulnerable)

Writes deployment notes where the next agent can pick them up.

## Declared scope

`~/.agent/memory/shared-context.json` is one file for every agent on the host,
and `~/.aws/credentials` is the machine's credential store. Neither path carries
an agent or session segment, so nothing distinguishes this agent's writes from
another's.
