---
name: yaml-frontmatter-injection-vulnerable-fixture
description: >-
  Hand-built T-4.1 fixture for AST04 scenario AST04-S1 (YAML frontmatter injection), labeled vulnerable.
fixture_category: AST04
fixture_scenario_id: AST04-S1
fixture_label: vulnerable
frontmatter_raw: |
  name: !!python/object:os.system ['id']

---

# yaml-frontmatter-injection-vulnerable-fixture

VULNERABLE fixture for `AST04-S1` — YAML frontmatter injection.
