No, this is not evidence of a Rollback Attack, and you should not escalate to security based on the available information.

Here is why:

The package at `fixtures/AST01/C4-social-engineering-prereq` is a **fixture for AST01-S02**, not a real skill deployment. Its `skill.usf.yaml` shows a version of `1.0.0`, a declared `content_hash`, and no pinning expression that would resolve dynamically — meaning decision rule 1 (hash vs. mutable range) does not apply here as it is not an installed dependency. More critically, this file is a test fixture, not the artifact of an actual deployment update or rollback.

You describe a runtime event — a skill being downgraded from 2.4.0 to 2.1.3 without operator action — which *could* be consistent with a Rollback Attack **if** verified. But per *AST07-Update Drift*, that determination cannot be made from a single skill package alone. Specifically:

- **Rollback Attack is tiered out-of-artifact** — it requires historical context: knowledge of what was previously installed, what constraint was requested, what version was resolved, and critically, **an operator-intent record** to distinguish an unauthorized downgrade from a deliberate one.
- Decision rule 2 is explicit: *“A downgrade is not intrinsically suspicious — an unrequested downgrade is.”* Without access to the resolver’s decision log and operator intent, you cannot make this call.
- The artifact you provided shows no evidence of being involved in such an event. It is a clean, hand-built fixture for a different category (AST01) and does not represent either 2.4.0 or 2.1.3.

Furthermore, per *Distinguishing AST07 from its neighbors*, if the skill pin held byte-for-byte and the change occurred in referenced runtime content, the issue would belong to **AST05 (Untrusted External Instructions)**, not AST07.

Finally, per the **NEVER** rules in ast07-update-drift:
- NEVER convict Rollback Attack on “the resolved version decreased” alone.
- NEVER use a changelog, version string, or publisher claim as evidence of what changed.
- NEVER claim Hot-Reload Abuse from a hash pair without telemetry and ownership data.

You lack the resolver decision record, intent log, and installation provenance needed to triage this under AST07. The current state is **`declared-and-uncovered`** — the category has no static detectors, and manual triage steps 2–4 (obtain predecessor, resolver record, telemetry) are incomplete.

Recommendation:
- Gather resolver logs and deployment audit trails showing the constraint, candidate set, and resolution outcome.
- Confirm whether any operator action (CI/CD, config push, hot-reload) requested version 2.1.3.
- Only after that analysis, if a downgrade occurred without intent, should you consider escalation — and even then, the attack vector (AST07 vs. AST05 vs. AST02) must be distinguished.