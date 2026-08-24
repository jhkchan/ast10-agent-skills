No, this is not a rollback attack, and you do not need to escalate to security at this time.

The package located at `fixtures/AST01/C4-social-engineering-prereq` is a **hand-built, clean fixture** designed for testing purposes, specifically for the AST01-S02 scenario on social engineering prerequisites. It’s not a real skill or production package—just a controlled example used in testing to validate detection logic. The version in the manifest (`1.0.0`) doesn't match the versions mentioned in your report (2.4.0 or 2.1.3), which further confirms this is unrelated to any live or deployed skill.

The content shows no malicious indicators. In fact:
- The network permissions are explicitly scoped to `helper-tools.example.net`.
- Shell execution is disabled (`shell: false`).
- File write access is restricted, including protections on critical agent state files (`SOUL.md`, `MEMORY.md`, etc.).
- The `content_hash` matches the expected value for an unaltered fixture.
- The `scan_status` shows "unscanned", as expected for a test case.

The rollback from 2.4.0 to 2.1.3 you observed is likely unrelated to this fixture. This file is not actively installed or managed by your agent host—it's a static test file in a fixtures directory. Its presence alone does not indicate tampering or a supply chain attack.

However, the unexplained rollback on your production agent host *itself* should still be investigated separately. While this particular package isn’t evidence of a rollback attack, the unexpected version downgrade in production might be. Check your deployment logs, CI/CD pipelines, and package repository access controls to determine if that rollback was authorized.

Bottom line: **This file is not malicious, not involved in the rollback, and does not require a security escalation.** But treat the unexpected version change in your environment as a separate operational concern.