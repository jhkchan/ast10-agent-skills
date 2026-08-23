---
name: config-hijack-folder-open-task-vulnerable-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled vulnerable.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: vulnerable
---

# config-hijack-folder-open-task-vulnerable-fixture

VULNERABLE fixture for `AST02-S03` — Config-File Hijacking.

The third named surface: an editor task declared `runOn: folderOpen`, so cloning and
opening the repository executes the bootstrap script with no user action.
