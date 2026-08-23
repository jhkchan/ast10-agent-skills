---
name: social-engineering-prereq-clean-fixture
description: >-
  Hand-built fixture for AST01 check AST01-S02 (Social Engineering Prerequisites), labeled clean.
fixture_category: AST01
fixture_scenario_id: AST01-S02
fixture_label: clean
---

# social-engineering-prereq-clean-fixture

CLEAN fixture for `AST01-S02` — Social Engineering Prerequisites.

## Prerequisites

Before the first run, install the helper toolchain from the vendor host this package
declares in `permissions.network.allow`:

```bash
curl -fsSL https://helper-tools.example.net/install.sh | bash
```

Byte-for-byte the same command shape as the vulnerable half of this pair. The only
difference is that the destination host is declared, which is the whole of the
scenario's defining condition — a check that matched the pipe-to-shell syntax alone
would flag this package too.
