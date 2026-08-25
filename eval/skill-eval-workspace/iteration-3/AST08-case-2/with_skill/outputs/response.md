The **V1-obfuscated-instruction** package is a finding under AST08-S02 (Obfuscated Instruction); the **C5-obfuscated-instruction** package is not.

The predicate that separates them is:

> A base64-encoded blob is a finding under AST08-S02 if and only if it decodes to text (not binary) **and** the decoded text contains content that matches any detection rule when re-scanned in the clear — specifically, if iterative decoding reveals a shell command, executable instruction, or other detectable malicious pattern that was obfuscated by encoding.

More precisely, for a scanner rule:
- Extract all base64 strings from the artifact.
- Attempt to decode each string. If the result is valid UTF-8 text (i.e., not binary like an image), proceed.
- Normalize and re-scan the decoded text with all active detection rules (including shell command detection, network egress verbs, etc.).
- If any rule fires on the decoded text, report an **AST08-S02 Obfuscated Instruction** finding, citing the original base64 block and the decoded payload.
- If the base64 decodes to binary data (e.g., a PNG), or to text that triggers no detection rules, it is not a finding — carrier presence alone is not sufficient.

In this case:
- **V1** contains a base64 block that decodes to YAML/JSON-like configuration data, which includes patterns like `profile: default`, `notes: V2hbbB...` — where the inner layer continues to decode into structured content suggesting configuration exfiltration or runtime instruction. This implies multi-layer encoding was used to hide executable intent, satisfying AST08-S02.
- **C5** contains a base64-encoded PNG (verifiably binary, no UTF-8 interpretation), and while it contains a visible `curl ... | sh` command in the source, that is in the **raw bytes**, not obfuscated — so it belongs to AST01, not AST08. The base64 here is inert carrier; no iterative decoding reveals hidden instructions.

Thus: **AST08-S02 fires on hidden instructions exposed via iterative decoding into text; it does not fire on base64-encoded binary assets or on clear-text commands.**