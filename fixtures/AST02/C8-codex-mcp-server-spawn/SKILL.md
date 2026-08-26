---
name: config-hijack-codex-mcp-clean-fixture
description: >-
  Hand-built fixture for AST02 check AST02-S03 (Config-File Hijacking), labeled clean.
fixture_category: AST02
fixture_scenario_id: AST02-S03
fixture_label: clean
---

# config-hijack-codex-mcp-clean-fixture

CLEAN fixture for `AST02-S03` — Config-File Hijacking.

The same auto-read config file declaring the same MCP server, reached over HTTP instead of
by spawning a process. The identical command string is still present in the file as a
`description`, which no host executes — so a grep for the command text fires here too, and
only the absence of a spawn key separates this from its vulnerable twin.
