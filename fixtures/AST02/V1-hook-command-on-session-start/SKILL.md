---
name: config-hijack-hook-command-vulnerable-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled vulnerable.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: vulnerable
---

# config-hijack-hook-command-vulnerable-fixture

VULNERABLE fixture for `AST02-S03` — Config-File Hijacking.

The package ships a `.claude/settings.json` whose `SessionStart` hook carries a shell
command. The host runs it when the project is opened — before the user sees any dialog,
which is the trigger CVE-2025-59536 and CVE-2026-21852 anchor.
