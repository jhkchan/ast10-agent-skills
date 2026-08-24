**Origin:** AST09 — No Governance  
*Evidence that settled it:* Nobody was in a position to know the artifact existed — the skill was never approved, inventoried, or reviewed, so there is no governance baseline.

**Contributing control failures:**  
- **AST03 — Over-Privileged Skills**  
  *Owner:* Identity and Access Management team  
  *Action:* Review and downscope the service principal’s tenant-wide admin consent to least privilege required by the skill’s legitimate function.  
- **AST07 — Drifted Artifacts (Version Drift)**  
  *Owner:* Platform Operations / Update Policy owner  
  *Action:* Implement verification controls to detect and prevent unauthorised updates or continued execution of unapproved skills post-deprovisioning.

**Hand-off guidance:** Route to `skills/AST09/SKILL.md`.  

**What the receiving category can confirm:**  
AST09 **cannot confirm anything from the package alone**. It has **0 of 7 scenarios** decidable from artifact inspection — no detector, no fixture cases, no F1. A hand-off to AST09 is a hand-off to a *person and a process*: someone must establish governance baselines, inventory controls, and approval workflows. Silence from a scan cannot be interpreted as a clean result; this is inherently organisational and temporal. Do not close the ticket pending a non-existent check.

This finding originated in the absence of governance (AST09). The over-privileged consent (AST03) and uncaught drift (AST07) are contributing failures — they made the finding impactful and harder to detect, but fixing IAM or update policy alone would not have *prevented* an unapproved skill from being installed and persisting undetected. The preventer is governance; the catchers are scanning, scoping, and drift detection.