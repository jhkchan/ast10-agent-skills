**Origin AST id:** AST09  
**Evidence that settled origin:** Nobody was in a position to know the artifact existed — the skill was never approved, inventoried, or reviewed, so there is no governance baseline.

**Contributing control failures:**
- **AST03** — Over-Privileged Skills  
  **Owner:** Cloud identity and access management (IAM) team  
  **Action:** Review and remediate the excessive scope of the service principal’s tenant-wide admin consent, even if the skill’s declared permissions were minimal. The grant is too broad for the operational context.
- **AST07** — Missing Version Control  
  **Owner:** Platform operations / update policy owner  
  **Action:** Investigate whether the currently running skill matches the version (if any) that may have been informally approved. Establish verification to detect drift, though the absence of a baseline makes drift unmeasurable.

**Hand-off target:** `skills/AST09/SKILL.md`

**What the receiving category can actually confirm:**  
**Nothing from the package alone.** AST09 has **0 of 7** detectable scenarios (`declared-and-uncovered`). The category addresses organisational and procedural failures — lack of approval, absence from inventory, undetected persistence — none of which are encoded in the skill artifact. A hand-off to AST09 routes to a **person and a process**, not a file or a detector. The responsible party must be identified to establish governance controls retroactively and prevent recurrence.

**Unrouted?** No — origin is settled: the absence of governance is the condition that had to be true first. The over-privilege and version drift are meaningful *only* because the skill was invisible to oversight.