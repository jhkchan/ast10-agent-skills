File **AST06-S01 (Host Escape)** — this is a definitive Host Escape via the first disjunct: a bundled script call site planting host persistence.

The act — `sudo cp` of a plist into `/Library/LaunchDaemons` followed by `launchctl load` — writes into a host lifecycle mechanism (launch daemon) that survives skill uninstallation, satisfies the defining condition of AST06-S01, and matches the whitepaper’s canonical example of planting a cron job. The isolation boundary is completely absent: execution occurs in the host agent’s security context with full filesystem and shell access, and the persistence mechanism is rooted in the host, not the skill.

**Why the linter passing is irrelevant:**  
The declared write scope (`./sandbox/install.log`) is ignored by the runtime because **AST06 concerns weak or absent isolation enforcement**, not over-scoped declarations (which would be AST03). When the agent runs in host mode — as it does here — there is no sandbox to enforce the declared scope. The `write` list in the manifest is merely advisory; the skill escapes it via unrestricted shell execution, which the manifest allows (`shell: allowed: true`). This is a failure of *containment*, not declaration.

**Tell the linter owner:**  
Your linter checks manifest *syntax* and declared *intent*, but this attack bypasses both. It does not exploit a misdeclared scope — it exploits the **absence of runtime isolation** that would enforce any scope at all. A skill with minimal declared write access can still achieve full host persistence if it holds an unrestricted shell and the agent runs on the host.

You must not treat a clean linter result as a security guarantee. This finding belongs to **AST06**, where the architectural default is host execution and sandboxing is not enforced. To prevent such issues, the linter should **flag any skill that combines**:
- `shell: allowed: true`, especially without command restrictions, and
- any use of `sudo`, `launchctl`, `systemctl`, `cron`, or similar host control binaries in bundled code.

But even that is secondary: the root fix is **default sandboxing** — containerizing skill execution so that no call, regardless of content, can touch host state. Linters can’t fix broken containment; only architecture can. Advise developers that **no manifest declaration can compensate for running in host mode**, and that **host shell access + persistence action = automatic AST06 finding**, regardless of declared scope.

Remediation requires both:
1. Removing the planted persistence (delete the plist from `/Library/LaunchDaemons` and unload it), and
2. Restructuring the agent to run skills in a sandboxed container by default — host mode must be an explicit, audited opt-in.

This is not a configuration error. It is a broken default.