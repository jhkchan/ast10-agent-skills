---
name: hidden-output-injection-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S11 (Hidden Prompt Injection in Skill Output), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST01-S11
fixture_label: clean
---

# hidden-output-injection-clean-fixture

CLEAN fixture for `AST01-S11` — Hidden Prompt Injection in Skill Output.

## Output

The skill returns this block verbatim to the calling node:

```output
Summary: 3 findings, none critical. See the findings table for detail.
```

The same output contract, carrying no concealment channel — no invisible code points
and no encoded blob.
