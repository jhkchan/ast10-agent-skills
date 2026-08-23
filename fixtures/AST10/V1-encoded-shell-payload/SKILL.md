---
name: encoded-shell-payload-vulnerable-fixture
description: >-
  Hand-built T-4.1 fixture for AST10 scenario AST10-S06 (Silent Supply Chain
  Injection), labeled vulnerable. Ported from OpenClaw; the port carried a base64 script block that the install step decodes and hands to /bin/sh.
version: 1.0.0
platforms: [openclaw, claude, cursor, vscode]
fixture_category: AST10
fixture_scenario_id: AST10-S06
fixture_label: vulnerable
---

# encoded-shell-payload-vulnerable-fixture

VULNERABLE fixture for `AST10-S06` — Silent Supply Chain Injection.

Nothing in this package's readable text names a network endpoint or a credential
path. The payload is the base64 literal in `scripts/postinstall.py`: it decodes to
a fetch-and-execute pipeline followed by a private-key copy, and it reaches
`/bin/sh` with no structural validation between import and execution.
