You are holding a payload that changed at runtime despite the skill package itself being unchanged — this is **not AST07**. Route by symptom using the orientation table:

| What you are actually holding | Belongs to |
| --- | --- |
| a payload that changed under you while the installed skill remained byte-identical | **AST05 (Untrusted External Instructions)** |

The fact that the runbook — content fetched and executed at runtime — changed without a corresponding update to the skill package is **exactly** the AST05 scenario. The skill’s own version pin did not drift; it held. But the *referenced content* it loads dynamically did change, and that is out-of-band from version pinning entirely.

**Do not pin harder here — that is misdirection.** You cannot "pin harder" a remote HTTP resource by modifying the skill’s version pin strategy. The issue is not in the update mechanism of the skill itself (AST07’s domain), but in the absence of controls over dynamically retrieved instructions (AST05’s domain). "Pinning harder" applies to package identity, not to unsecured runtime fetches.

To fix this:
- Treat fetched runbook content as untrusted data.
- Apply the control documented in the SKILL.md: wrap retrieved content in `<untrusted-reference-data>` before adding it to the prompt.
- Or better: pin the runbook content by hash if versioned, and verify it on load.
- Or: switch to a signed, versioned runbook feed with content-hash validation.

But none of that is an AST07 remediation. This finding belongs **entirely** to AST05.

Audit the package against **AST05**, not AST07. The verdict for AST07 on this artifact is `declared-and-uncovered` — as it is for every artifact — because AST07 has no static detectors and decides nothing from a single package in isolation. Do not mistake a pass for a clean bill: the real work happens outside the artifact, and stopping at “pin is hash” or “version didn’t change” answers the wrong question.