You're right to feel uneasy — this is not AST03. It's **AST09 - No Governance**, specifically scenario **S03: Orphaned Skill** (a departed employee’s still-active, still-credentialed skill).  

Here’s why the draft misroutes it:  
- **AST03 (Over-Privileged Skills)** applies when a *currently governed* skill has a manifest that grants more permissions than needed. The fix is narrowing the declared scope — a package-level change.  
- But here, the issue isn’t the *design* of the skill; it’s that **no governance process ever asserted control over it**. There’s no record of approval, no inventory entry, and critically, **no revocation triggered by offboarding**. The credential is still active *because the workflow to remove it doesn’t exist or wasn’t connected to HR offboarding*.  

The "pending package scan" status compounds the error — a scan might detect the skill now, but it doesn’t fix the systemic gap: **skills are not being deprovisioned when employees leave**. That’s an *organizational control failure*, not a package flaw.

### Correct action:
**Do not reduce the scope — revoke the credential entirely and uninstall the skill.**  
Then, **mandate integration of skill revocation into the offboarding workflow**.  

That means:  
- HR offboarding → triggers revocation of all non-human identities (NHIs) provisioned by the employee  
- Automated reconciliation of connected apps/SaaS grants against active directories  
- Audit log of both the revocation *and* the workflow execution  

Why? Per **Decision Rule 6**: Orphaned Skill is routine, not incident-driven. Fixing it *once* as AST03 makes it look like a one-off permission tweak. Fixing it as AST09-S03 forces the process change that prevents recurrence every time someone leaves.

### Reporting:
Do **not** write "AST03: fix via scope reduction".  
Instead:  
> **Finding**: AST09-S03 (Orphaned Skill) — `invoice-sync` remained credentialed post-offboarding with no inventory or revocation trace.  
> **Root Cause**: Offboarding workflow lacks integration with NHI lifecycle management.  
> **Action**: Revoke credential, uninstall skill, and require identity-aware offboarding automation.  

This correctly frames it as a *governance gap*, not a *package misconfiguration*. The credential wasn’t “over-scoped”—it was *orphaned*, and that’s on the process, not the code.