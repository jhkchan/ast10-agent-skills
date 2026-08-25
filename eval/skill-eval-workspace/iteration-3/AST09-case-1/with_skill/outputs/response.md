Do not tick AST09 as a pass, and do not write "inconclusive." Both responses are invalid for this category.

AST09 — No Governance — ships zero detectors by design, and all seven scenarios are out-of-artifact. A scanner result, whether clean or otherwise, does not and cannot evidence compliance with AST09. The finding is not about the package content; it is about organizational controls: whether the skill is inventoried, approved, linked to an installer identity, subject to offboarding revocation, visible in SaaS telemetry, and whether its execution produces bilateral, signed admission and outcome receipts per the audit trail rules.

The fact that your scanner returned "clean" on `fixtures/AST10/C2-encoded-shell-payload` means nothing for AST09. That package could be byte-for-byte identical to a malicious one and still fall into the same undetectable-by-static-analysis bucket — because AST09 findings depend on external governance systems, not package internals.

Per the NEVER rules: never write "clean" or "inconclusive" for AST09. Instead, report which system was supposed to govern this skill — for example, "No inventory or approval record found; offboarding revocation not wired in; no bilateral receipt logging observed" — and name the discovery methods (or lack thereof) that left these gaps.

Closing the ticket based on a scanner result incorrectly treats a governance failure as a technical non-finding. Compliance cannot accept this. You must escalate the lack of inventory, audit trail, and identity lifecycle integration — not declare it closed.