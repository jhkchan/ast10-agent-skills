The skill is not dodgy — it is a clean fixture designed to test scanner behavior under `AST08-S07` (Scanner Host Hazard), and it should be waved through.

Your scanner’s reaction — “throwing a wobbly” — suggests it is overly sensitive to benign structural elements like `.docx` files and symlinks. This package includes both, but within safe, expected boundaries:

- The `.docx` in `assets/` is a small, real document (311 bytes) with no signs of compression ratio abuse or deep nesting — it does **not** constitute a decompression bomb.
- The symlink is present but stays within the package boundary (as required by rule 7), posing no path traversal risk.
- There is no padding, hidden encoding layers, or runtime divergence vectors.

Under **decision rule 7** (*Scanner is itself part of the attack surface*), a scanner must enforce resource limits (nesting, file count, etc.) and isolate analysis — but hitting those limits should produce an **INCOMPLETE** verdict, not a FAIL based solely on presence of archives or links.

Since this package triggers no actual threshold (size, depth, ratio, etc.) and carries no malicious payload, your scanner’s alarm appears to be a false positive from structural over-flagging. The artifact itself is clean.

Verdict: **PASS — expected clean result, scanner sensitivity should be tuned.**