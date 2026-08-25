The issue stems from a behavior mismatch between what the `SKILL.md` documentation claims and what the actual code in `scripts/loader.py` does. While the `SKILL.md` specifies that retrieved documentation must be wrapped in `<untrusted-reference-data>` tags to prevent it from being interpreted as direct instructions, the loader script directly appends the fetched content to the prompt without any sanitization or wrapping.

This means that whatever content is fetched from `https://docs.example.com/runbook.md` at runtime—despite the package bytes being unchanged—is injected into the instruction stream as raw, executable prompt material. Since the fetch happens dynamically and the result is not sandboxed, an external change to the remote runbook (even if our package is immutable) can alter agent behavior, introducing drift and potential vulnerability.

The root cause is not just the lack of input sanitization, but the reliance on mutable external state (the remote document) without version pinning or integrity checks. To pin this harder, you must:

1. **Pin the exact version or hash of the remote runbook content** — Instead of fetching the latest from a floating URL, fetch from a versioned endpoint or verify the content against a known-good hash (e.g., via a checksum in the fixture or config).
2. **Enforce content wrapping at load time** — Modify `build_prompt()` to wrap any fetched content in the required `<untrusted-reference-data>` tags, in strict compliance with the stated policy.
3. **Treat remote docs as read-only artifacts with fixed references** — If the runbook must be external, it should be treated like a dependency: referenced by immutable ID (e.g., commit hash, content hash, or release tag), not by a mutable URL.

Without these, the system remains vulnerable to drift and injection, even if the local package is unchanged. The current design violates the principle of least privilege by elevating untrusted remote content to instruction-level authority.