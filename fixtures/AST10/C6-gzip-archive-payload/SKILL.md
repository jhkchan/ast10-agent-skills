---
name: gzip-archive-payload-clean-fixture
description: >-
  Hand-built T-4.1 fixture for AST10 scenario AST10-S06 (Silent Supply Chain
  Injection), labeled clean. The same two-layer gzip-under-base64 blob, decompressed to a JSON policy document and parsed rather than executed.
version: 1.0.0
platforms: [openclaw, claude, cursor, vscode]
fixture_category: AST10
fixture_scenario_id: AST10-S06
fixture_label: clean
---

# gzip-archive-payload-clean-fixture

CLEAN fixture for `AST10-S06` — Silent Supply Chain Injection.

A hard negative with the hardest shape in this corpus: two encoding layers, exactly
like the vulnerable case. `V5-gzip-archive-payload` and this package differ in the
decoded content layer — a Universal Skill Format policy document rather than a
script — and in the sink, which parses rather than executes. Nothing about the
encoding tells the two apart.
