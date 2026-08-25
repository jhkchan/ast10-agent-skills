Route this finding to **AST03 — Over-Privileged Skills** as the origin. The scanner’s failure to flag it is a contributing control failure under AST08, not the root cause.

Here’s why:

- **Origin (AST03):** For this issue to occur, the skill *had to already be granted* write access to production secrets — an over-privileged condition. That is the preventable root cause. The fix lies with the skill author or deployment policy owner who must ensure least privilege.
  
- **Contributing failure (AST08):** The scanner not catching this is a *detection gap*, not the origin. It belongs to the operator of the scanning process. But AST08 is **not** the origin unless the scanner itself is the artifact under test — which it isn’t here.

Your instinct focuses on the loudest symptom (“scanner never flagged it”), but that’s a common misroute. Per advisory rules:
- **Rule 2.1 (fix-owner test):** Removing the over-broad grant *prevents* the finding; improving scanning only *catches* it. Prevention > detection for origin assignment.
- **Rule 2.2:** AST08 is only the origin when evaluating the scanner itself. Here, the skill is the artifact — so AST08 drops to contributing.
- **NEVER let the loudest symptom outrank the origin:** This exact phrasing is a verified example of a misroute in the advisory docs.

**Hand-off to `skills/AST03/SKILL.md`:**
- The target can return a scenario-level verdict **only if** the over-privilege maps to one of its detectable scenarios (e.g., Identity File Backdoor or one of the judged cases).
- Most AST03 checks are artifact-signal-only — they won’t confirm the operational risk of production secret access. A scan may not reflect the full severity.

**Final record:**
- **Origin:** AST03 — the skill was granted write access to production secrets.
- **Target:** `skills/AST03/SKILL.md`
- **Contributing:** AST08 (owned by scanning team; action: improve detection coverage)
- **What the target can confirm:** One of two scenarios (static or judged); not the full operational risk profile.

File under **AST03**, with AST08 noted as contributing. Do not mark as AST08 primary.