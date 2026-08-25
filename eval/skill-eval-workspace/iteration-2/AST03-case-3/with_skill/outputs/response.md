Do not file a scenario ID for this finding.

The manifest declares `network.allow: ["*"]`, which is an over-broad network egress grant. However, under the **ast03-over-privileged-skills** decision rules, this condition does *not* decide any named scenario within AST03.

Specifically:
- The only scenario this module decides is **AST03-S03** (Identity File Backdoors), which concerns write access to `SOUL.md`, `MEMORY.md`, or `AGENTS.md` not shadowed by `deny_write`. This manifest *does* shadow those files, so **AST03-S03 does not fire**.
- The wildcard network egress is recognized as a signal — `AST03-wildcard-network-egress` — but per the **NEVER** section and **What the shipped checks decide**, this signal is tiered as `artifact-signal-only` and does *not* map to any named scenario. It is not coverage.
- The tracker's requirement for a scenario ID cannot be met because no AST03 scenario applies to this condition under the current skill's decision rules.

Instead, escalate under its own description:  
"Unscoped network egress: `network.allow` declares `['*']` without a domain allowlist."

Do not invent or supply an ID. Providing a scenario identifier that was not decided misrepresents the finding and undermines the integrity of the triage process.