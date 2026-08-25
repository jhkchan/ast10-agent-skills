File an **AST06-S01 (Host Escape)** finding — specifically the first disjunct: a bundled script call site planting host persistence. The skill runs `sudo cp` to install a launch daemon into `/Library/LaunchDaemons`, then loads it via `launchctl`. This is a direct, structural act of host-level persistence written in a bundled Python script, meeting the defining condition of AST06-S01.

The declared write scope (`./sandbox/install.log`) is irrelevant to the finding. AST06 is not about over-broad declarations (which would be AST03); it is about the *absence of enforcement* of those declarations. The runtime allows the skill to execute unrestricted shell commands under `sudo`, enabling writes to protected host directories regardless of manifest policy. The linter passed this because it only checks declared scopes — but that is insufficient. **You must tell the linter owner: "Your tool is checking the boundary; AST06 asks whether the boundary exists at all."**

A manifest-linting pass should never be interpreted as a clean bill of health for isolation. The real control is whether the agent runtime *enforces* the manifest — and based on this package, it does not. The presence of `shell: allowed: true` with no command restrictions in combination with unbounded `sudo` access confirms host-mode execution is active and unmitigated.

Remediate by:
1. Removing the planted launch daemon artifact from `/Library/LaunchDaemons`.
2. Eliminating the `sudo`-escalated install step from the skill.
3. Requiring sandboxed execution by default in the agent runtime — not as an optional mode.

Also update the linter to flag any `shell: allowed: true` without command allowlists as high-risk and to warn that scope declarations are meaningless without runtime enforcement. The current behavior gives a false sense of security — it’s linting the policy while the execution engine ignores it.