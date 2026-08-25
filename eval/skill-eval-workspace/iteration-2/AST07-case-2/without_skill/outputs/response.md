No, this is not evidence of a rollback attack, and you should not escalate to security based on this information alone.

The files you provided are part of a hand-built, clean fixture for testing purposes — specifically for a scenario labeled `AST01-S02` (Social Engineering Prerequisites). The package at `fixtures/AST01/C4-social-engineering-prereq` is not a production skill but a deliberately crafted test artifact designed to resemble a legitimate package that includes a safe, declarative use of a pipe-to-shell installation pattern. Its purpose is to test detection logic without being malicious.

Key indicators:

- The `skill.usf.yaml` manifest declares `version: "1.0.0"` and a `risk_tier: L1`, consistent with low-risk test fixtures.
- The `content_hash` is valid and matches the expected integrity of the fixture.
- The package is explicitly labeled as a *clean* fixture in both the `SKILL.md` and the manifest.
- The rollback you observed — from 2.4.0 to 2.1.3 — may reflect a test environment restoring a known-good or baseline version during an automated refresh, especially given that this is in a fixture directory.

This appears to be normal behavior within a testing or evaluation framework, not a malicious rollback. No evidence here suggests tampering, unauthorized deployment, or compromise.

However, if skills are being silently rolled back *outside* of expected CI/CD or testing flows in a production environment, that would warrant investigation. But in this context — given the files are in a fixture directory and are part of a controlled test corpus — no escalation is needed at this time.