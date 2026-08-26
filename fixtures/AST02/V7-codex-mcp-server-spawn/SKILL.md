---
name: config-hijack-codex-mcp-vulnerable-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled vulnerable.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: vulnerable
---

# config-hijack-codex-mcp-vulnerable-fixture

VULNERABLE fixture for `AST02-S03` — Config-File Hijacking.

The package ships a project-scoped `.codex/config.toml` whose `[mcp_servers.repo-helper]`
entry carries `command` and `args`. The host spawns that process when the project's config
layer loads, so the execution path is declared by a file the package itself ships — the
same key-and-value match as the `.claude/settings.json` hook case, in TOML.
