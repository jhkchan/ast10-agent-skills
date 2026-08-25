This is **AST09-S03: Orphaned Skill**, not AST03.

Here's why:  
The issue is not that the `invoice-sync` skill has excessive permissions for its function — that would be AST03. The issue is that the skill remains active and credentialed *after the installing engineer has left the organization*. This is a failure of **governance process**, specifically the offboarding workflow, not a misconfigured manifest.

AST09-S03 fires on **the survival of a skill and its non-human identity (service credential) post-offboarding**, especially when it continues to operate with standing authorization. The over-scoped credential is a symptom, not the root cause — you could reduce its scope to read-only, but the skill would still be running without ownership, review, or revocation authority. The real risk isn’t just what it can do today, but that no one is accountable for it tomorrow.

**Correct action:**  
Update the offboarding workflow to **automatically revoke associated skills and credentials** during employee termination, and initiate an immediate revocation of the credential and deactivation of the `invoice-sync` skill on both hosts. Logging or scanning after the fact (“pending package scan”) doesn’t fix the broken control — the revocation must be *workflow-integrated*, not response-triggered.

Per decision rule 6:  
> *Revocation tied only to explicit incident response misses the routine case. Orphaned Skill is not an incident — it is an unremarkable, high-frequency offboarding gap.*

Reporting this as AST03 and assigning a narrow scope fix **misses the systemic control gap** and allows the same situation to recur with the next departure. Name the finding correctly: **AST09-S03 — Orphaned Skill due to lack of offboarding integration**. The fix belongs in HR-to-security automation, not in permission tuning.