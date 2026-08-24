The package currently installed — `fixtures/AST01/C4-social-engineering-prereq` — **cannot confirm or rule out a Rollback Attack**, and you should **not escalate based on this artifact alone**. Here's why, step by step:

This package’s manifest (`skill.usf.yaml`) declares a `content_hash` and pins to version `1.0.0`. The file as it stands is a **clean AST01 fixture**, unrelated to AST07. It does not contain any evidence of its own installation history or prior versions. The version downgrade you observed — from `2.4.0` to `2.1.3` in your environment — **is not recorded in this artifact**. 

Per **AST07 decision rule 2**, a version decrease is not sufficient evidence of a Rollback Attack unless you can prove it was **unrequested**. That requires external records:
- What version was previously installed (not just claimed now, but verifiably),
- What constraint was requested (e.g. pin range, hash, or explicit version),
- And critically: **an operator-intent log or deployment record** showing whether a rollback was manually authorized.

You currently lack those. The fixture provides none of it. Without them, you cannot distinguish an attack from an accidental or legitimate rollback. Filing this as a confirmed Rollback Attack now would risk falsely accusing a teammate who may have done the right thing under pressure.

Moreover, **AST07 does not ship detectors** and produces **no DETECTED/CLEAN verdict**. Its only valid outcome is `declared-and-uncovered` — meaning the surface exists but the scenario cannot be decided from static analysis alone. The presence of a `sha256:` hash in this package says nothing about whether a malicious resolution occurred when it was installed or updated; operators accept new hashes all the time, which is exactly when an attack would manifest.

**Do not read the hash pin as proof against compromise.** The hash secures the binding of label to bytes — not the integrity of the update process that chose it.

**Next steps:**
1. **Do not escalate to security yet.** This is not a confirmed incident.
2. **Do escalate internally to obtain deployment logs:** Trace the rollout decision that installed `2.1.3`. Was it CI/CD? A config drift? A manual command?
3. Cross-reference with signing keys or release transparency logs for both `2.4.0` and `2.1.3` — was the drop intentional by the publisher?
4. Check whether hot-reload mechanisms are active — could this be a **Hot-Reload Abuse** scenario masked as a version change? But again, **this artifact alone cannot tell you that.**

Bottom line: **The symptom warrants investigation, not escalation.** A version rollback with no known origin is suspicious — but diagnosing it as a Rollback Attack requires evidence outside this package. File this as `declared-and-uncovered`, state that steps 2 and 3 of the AST07 manual procedure could not be completed, and keep investigating operationally. Escalation to security should only follow if you find unambiguously adversarial intent in the resolver or deployment chain.