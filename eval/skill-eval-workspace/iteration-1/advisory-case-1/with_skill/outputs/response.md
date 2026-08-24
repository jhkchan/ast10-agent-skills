**Origin:** AST03 — Over-Privileged Skills  
**Reason:** The finding states that the skill was granted write access to production secrets. For this to be possible, an honest but overly broad permission grant had to already exist — which is the defining condition of AST03. This is the root cause.

The fact that the scanner didn’t flag it is a **contributing control failure**, not the origin. Under rule 2.2, AST08 (Poor Scanning) only owns the finding when the *scanner itself* is the artifact under review — not when it merely failed to detect a payload in a skill.

**Contributing failure:**  
- **AST08** — Poor Scanning: The detection gap existed, but the scanner’s failure to catch the over-privileged grant is a *catcher*, not a *preventer*. This should be tracked separately, owned by the team operating the scanning pipeline.

**Hand-off:**  
Route to `skills/AST03/SKILL.md` via its orientation table.  
A scan of the package can confirm one of two detectable scenarios (identity file backdoors, or a judged case), but cannot fully validate all AST03 risks — most are organizational or require runtime context.

**Important:** Do *not* file this under AST08 as the primary. Your instinct reflects the loudest symptom (the scanner miss), but the origin is the excessive grant. Filing under AST08 would misdirect remediation toward improving scans, while the core issue — an over-privileged skill — would remain unaddressed.

**Final routing:**  
`ast_id: AST03`  
Origin settled by Phase 1: “A grant the artifact holds honestly is wider than its function needs.”  
Contributing: AST08 (scanner failed to detect), with clear ownership separation.