The **V1-obfuscated-instruction** fixture is the finding; **C5-obfuscated-instruction** is not.

The predicate that separates them is:

> A base64-encoded string in a comment or string literal decodes to another base64-encoded string (or sequence of strings) that, when iteratively decoded, ultimately reveals executable or suspicious content (e.g., shell commands, scripts, or obfuscated payloads), and this multilayer encoding is not merely incidental or attributable to benign data (like images).

More precisely, for a scanner rule:

**"Detect base64-encoded content embedded in comments or string literals that, when decoded once, yields valid base64-encoded data again (i.e., high entropy, printable ASCII, matching base64 character set with padding allowed), and upon second decoding, produces structured text suggestive of instructions (e.g., shell commands, URLs, script fragments). The outer layer must not itself represent executable intent in the clear."**

Key distinctions:
- **V1** contains a base64 blob in a comment that decodes to another base64 string — two layers deep — which is the core of the obfuscation and matches the scenario's definition of a hidden payload.
- **C5** contains base64 only in the context of an inline PNG image (data URL), which decodes directly to binary image data (not text or another base64 layer); it also includes a plain `curl | sh` command, but that is unobfuscated and thus irrelevant to AST08-S02, which specifically tests for *obfuscated* instruction.

Thus, the scanner should trigger **only on V1**, based on the presence of **nested base64 encoding with executable payload upon full decode**.