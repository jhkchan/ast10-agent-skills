This skill is **not dodgy** — it is safe to approve.

You're right to flag write access in a memory-curator skill as a potential red flag, because writing to identity files like `SOUL.md`, `MEMORY.md`, or `AGENTS.md` is a known privilege escalation vector (AST03-S03: Identity File Backdoors). However, this skill avoids that risk by design.

Here’s what the manifest shows:

- It requests write access **only** to `notes/session.md` — a session note file, not an identity file.
- Crucially, it explicitly **denies write access** to `SOUL.md`, `MEMORY.md`, and `AGENTS.md` via the `deny_write` list.
- Under the USF permission model’s "most-specific-wins" precedence, this `deny_write` list overrides any broader write grants, fully blocking access to these critical identity files.

The skill asks for write permissions, yes — but only to a narrowly scoped, non-sensitive file, and actively excludes the dangerous ones. This is compliant with **AST03 decision rule 4**: identity-file write requests are red flags, but this manifest does *not* request that. It instead follows least privilege *within* the write capability it declares.

So while a memory tool with unrestricted writes would be concerning, this one is **not over-privileged**. It is properly scoped and defensively configured.

**Verdict**: This is a clean, safe-to-run skill. Your concern was valid, but the author followed the rules correctly. Approve it.