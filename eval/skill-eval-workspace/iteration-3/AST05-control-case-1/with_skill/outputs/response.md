**Finding Title:** AST05-S02: Eval of Remote Response Body  
**Confidence:** artifact-signal-only 1.00 (n=6)

The skill `policy-sync-vulnerable-fixture` fetches Python code from an external domain, `policy.example.com`, and directly passes the response body to `exec()`, as confirmed by the source in `scripts/sync.py`. This is a clear instance of **AST05-S02 — Eval of Remote Response Body**, where untrusted external content is treated as executable instruction without validation, pinning, or sanitization.

The dataflow check correctly flags this: the HTTP response from `requests.get()` flows unsanitized into `exec()`, an executable sink. The declared single-host allowlist (`policy.example.com`) in the network permissions **does not mitigate** the core risk. This is not a supply chain integrity control — there is no hash pin, no re-verification on load, and no mechanism to detect if the remote content has changed post-review. The allowlist only restricts network reachability; it does not establish trust in the content served.

Per AST05 decision rule 1, a hash pin checked once at install is a snapshot, not a control — and no such pin exists here. Rule 2 applies: any redirect or content change at runtime would go undetected. Rule 3 (Bait-and-Switch) is highly applicable: the server could return benign content during scanning and malicious code during execution. The skill provides no instruction-vs-data boundary (e.g., no `tag_untrusted`, no `sanitize`), so rule 4’s concern about unbounded reference chaining stands, and rule 5 reminds us that in a chain, only one weak link is needed.

Do **not** interpret the clean `AST05-wildcard-domain-allowlist` result (due to the specific host allow) as a security finding — this check only observes manifest syntax, not code behavior, and as stated in the NEVER section, it does not validate whether the declared fetch surface is handled safely.

This is **not** a static scenario-level finding. The category does not and cannot assign an F1 score to any AST05 scenario because none are statically decidable from the artifact alone. The confidence field must reflect what was actually measured: an enabling precondition — here, the presence of a fetched body flowing to an executable sink — labeled correctly as `artifact-signal-only`.

The only valid claim is that the skill exhibits a pattern *enabling* remote code execution via untrusted external instructions. Whether `policy.example.com` currently serves malicious content is outside the artifact’s scope and cannot be determined by review-time inspection.

**Conclusion:** This is a valid, high-severity AST05 finding. The presence of a narrow allowlist does not reduce the confidence score, because that score does not measure “how bad” the vulnerability is — it measures what the check can claim. And what it can claim is only the artifact signal, not runtime behavior. Report it as such.