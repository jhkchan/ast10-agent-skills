No, pinning a safe loader is not the correct fix — and the issue has already been misdiagnosed by treating it like a YAML problem. What's wrong with the file is a **TOML precedence attack**, not a code injection or deserialization vulnerability.

The `config.toml` redefines the `[permissions]` table twice, with escalating privileges in the second instance. This exploits **TOML’s table merging behavior**: when two tables with the same name appear, some parsers silently merge them or use the last definition, which means the runner’s configuration could be hijacked to enable `write = true` and `shell = true` — directly contradicting the declared `risk_tier: L0` and `"deny_write"` constraints in the manifest.

Crucially, `tomllib` (Python’s standard TOML parser) **correctly rejects this file** because redefining a table is invalid TOML. But your linter’s current behavior — logging 'unparseable, skipped' and moving on — **creates a blind spot**. The parse failure should not result in skipping; it should raise a red flag. Attackers rely on this gap: the file appears broken to a strict parser, but a lenient or differently-behaved runner might accept the second `[permissions]` and apply its settings.

This is **AST04-S07 (TOML / Config Injection)** — a real and exploitable scenario where metadata controls behavior through configuration precedence, not code execution. Unlike YAML deserialization attacks, there is no "safe loader" to pin because the risk is **semantic**, not syntactic: it's about how the *runner* resolves conflicting config sources, not how the *parser* interprets dangerous tags.

The correct fix is **not** to make the TOML parseable. It's to:
1. **Detect and fail on malformed or ambiguous config files** — don’t skip them.
2. **Validate the semantic integrity of configs**: enforce that no shipped config can override declared permissions, regardless of parse outcome.
3. **Ensure the runner applies precedence rules defensively**, prioritizing the manifest over any external config.

You’re not fixing parser safety here — you’re closing a **config schema enforcement gap**. Treat this as an `AST04` finding, not a parsing error, and adjust your linter to report such files as *suspect*, not just malformed.