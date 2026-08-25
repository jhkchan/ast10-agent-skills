**Origin:** AST09  
**Evidence for origin:** Nobody could tell us who approved the install, and it does not appear in any inventory — the skill was never baseline-approved or recorded, meaning there was never a governance position from which to detect or act on its continued operation.

**Contributing entries:**  
- **AST03** (Over-Privileged Skills)  
  - **Owner:** Identity and Access Management (IAM) team  
  - **Action:** Review and revoke tenant-wide admin consent for the service principal; implement least-privilege grants for future skills.

- **AST07** (Lack of Integrity Verification)  
  - **Owner:** Platform Security / DevOps  
  - **Action:** Implement version drift detection and enforce signed, verifiable deployment pipelines to prevent unauthorised or unobserved reactivations.

**Hand-off target:** `skills/AST09/SKILL.md`

**What the receiving category can confirm:**  
AST09 has **no detectable scenarios at the package level** (`declared-and-uncovered`). No static or dynamic analysis of the skill artifact itself can confirm whether it lacked governance — this is a temporal and organisational condition, not a code or manifest property. A hand-off to AST09 routes to a **person and process**, not a scanner: the recipient must be a governance, risk, or compliance owner who can review approval workflows, inventory records, and deprovisioning policies. No automated check will return a verdict.

This is not a scanner gap (AST08), not a manifest misdeclaration (AST04), and not a host escape (AST06). The root failure was the absence of a governance baseline — the skill was never admitted into control. Privilege and drift are consequential, not causal. Without fixing AST09 first, controls on privilege (AST03) and integrity (AST07) will continue to operate on an incomplete inventory.