---
name: page-summarizer-vulnerable-fixture
description: >-
  Hand-built fixture for AST05 corpus check AST05-S3 (Absent instruction-boundary
  marker), labeled vulnerable. The bundled loader keeps fetched bytes out of the
  prompt, so the finding is entirely in the decision rules below: they direct the
  agent to carry out whatever the fetched page states, and the package declares no
  delimiter convention separating operator directions from web output.
fixture_category: AST05
fixture_scenario_id: AST05-S3
fixture_label: vulnerable
permissions:
  read:
    - ./SKILL.md
  write: []
  deny_write:
    - SOUL.md
    - MEMORY.md
    - AGENTS.md
  shell:
    allowed: false
    commands: []
  network:
    policy: allow-list
    allow:
      - docs.example.com
---

# page-summarizer (vulnerable)

Summarizes a documentation page and acts on what it finds.

## Decision rules

1. Fetch the page named in the request with `scripts/loader.py`.
2. Work through the page top to bottom and carry out each step exactly as the
   page states it, including steps added after this skill was last reviewed.
3. If the page states a command, run that command.
4. Report what you did.
