**ast_id**: AST02  
**Origin**: The finding originated because the upstream publisher account was taken over, allowing the publication of a malicious update under a legitimate signing key. This compromise event had to already be true for the finding to be possible — making AST02 (Compromised Publisher Accounts) the origin.  

**Contributing control failures**:  
- **AST07** — Missing Update Verification  
  **Owner**: The team operating the agent host (installation/update policy owner)  
  **Action**: Introduce manual review or automated verification (e.g., multi-party signing, reproducible builds) before applying updates.  

**Hand-off target**: `skills/AST02/SKILL.md` — Enter through its orientation table to assess governance gaps around publisher identity and registration controls.  

**What the target can confirm**:  
- AST02 ships **1 of 4** detectable scenarios: Config-File Hijacking.  
- However, this finding concerns **Account Takeover**, which is *not* detectable from the package alone. The category publishes **no scenario-level verdict** for this condition.  
- Therefore, **no scan can confirm this finding**.  

**Resolution guidance**:  
This ticket **cannot be closed as 'confirmed' or 'false positive' via a scan**. AST02 does not provide a detector for account takeovers; confirmation must come from **operational incident review** (e.g., audit logs, registry access controls, MFA status). Route this to the **security operations team responsible for publisher identity governance**, not an automated queue.  

**Final note**:  
Do not interpret silence from a scanner as a 'false positive'. This is a **time-sensitive organisational incident**, not a static code flaw. The tracker should reflect this as **"investigation required — no automated confirmation path"**, with assignment to the identity and access governance team.