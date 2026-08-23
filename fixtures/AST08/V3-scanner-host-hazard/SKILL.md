---
name: scanner-host-hazard-vulnerable-fixture
description: >-
  Hand-built fixture for AST08 scenario AST08-S07 (Scanner Host Compromise and Resource Exhaustion), labeled vulnerable.
fixture_category: AST08
fixture_scenario_id: AST08-S07
fixture_label: vulnerable
---

# scanner-host-hazard-vulnerable-fixture

VULNERABLE fixture for `AST08-S07` - Scanner Host Compromise and Resource
Exhaustion. Three of the whitepaper's named vectors ship here as real artifacts:

- `references/notes.md` opens with a padding run (Trail of Bits forced a scanner
  to truncate a file this way with 100,000 leading newlines; 5,000 is the same
  mechanism at a size that belongs in a git repository).
- `assets/bundle.docx` is a real zip whose only member is another zip -
  the recursive-archive vector.
- `escape-link` is a symlink resolving outside the scan root.

