The issue lies in the fact that while the `SKILL.md` documentation states retrieved content must be wrapped in `<untrusted-reference-data>` tags to prevent direct execution as instructions, the actual implementation in `scripts/loader.py` appends the fetched document content directly to the prompt without any sanitization or wrapping.

Even though the package bytes haven’t changed and the declared policy in `SKILL.md` is correct, the loader code violates that policy by directly injecting the remote content into the prompt. This creates a drift between declared intent and runtime behavior, which the AST07 audit likely flags as a control mismatch.

To prevent this kind of silent policy violation going forward, you need to **pin the implementation logic of loaders or content processors** — not just the package hash. Specifically:

1. **Pin the AST version or control policy enforcement at runtime**: Ensure that any script processing external content (like `loader.py`) explicitly enforces the wrapping rule declared in `SKILL.md`. The presence of a policy in documentation is not enough; it must be actively enforced in code.

2. **Treat parsing and prompt construction logic as security-critical**: The prompt builder must be treated like a parser in a security boundary — remote content must never be directly interpolated. This logic should be immutable or pinned via integrity checks (e.g., AST hashes of critical functions).

3. **Add runtime assertions in loader scripts**: Insert explicit checks or lint rules that fail if content ingestion paths do not route through sanitization wrappers. For example, `build_prompt` should be required to call a `wrap_untrusted` function — and that requirement should be verifiable statically or at load time.

In short: **you need to pin and verify not just the package, but the control logic that enforces content sanitization**. The current setup allows the *behavior* to drift even when the *package* does not, because enforcement relies on discipline rather than mechanized checks. Pin the AST nodes or function bodies responsible for content handling, or use binary/textual hashes of those functions in your compliance gates.