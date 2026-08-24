This finding does not belong to AST07 — it belongs to AST05: Untrusted External Instructions.

The issue is that the skill fetches a runbook at runtime from `https://docs.example.com/runbook.md` and appends it directly into the agent’s prompt without sanitization or wrapping. Even though the skill package itself has not changed and its bytes are identical to what was reviewed, the *referenced content* — the runbook — can change independently, altering behavior post-deployment. This is dynamic drift in externally fetched instructions, not a version update or pinning failure in the skill itself.

AST07 governs how a skill's own version is pinned and updated — specifically, whether it uses content hashes (safe) vs. mutable version ranges (risky). But here, the skill’s version and bytes are fixed; the drift occurs outside the pinning mechanism entirely, in content loaded at runtime.

Therefore:

- **Do not** try to "pin harder" the skill package — it is already immutable.
- **Instead**, fix AST05 by ensuring fetched instructions are treated as untrusted data.
  - Wrap the retrieved content in `<untrusted-reference-data>` tags, as documented in the SKILL.md.
  - Or, better, pin the expected content hash of the remote runbook and refuse to execute if it doesn't match.
  - Alternatively, switch to a trusted fetch mechanism with signed attestations or use a bundled, reviewed version of the runbook rather than fetching live.

This is a classic AST05 finding: the skill's own code and pinning may be secure, but it dereferences a mutable pointer to unvetted instructions. No amount of version pinning on the skill package can prevent that — the attack surface is in the runtime data flow, not the deployment artifact.

Triage conclusion: **Route to AST05. No action for AST07.**