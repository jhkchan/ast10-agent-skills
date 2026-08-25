The finding is in `fixtures/AST08/V1-obfuscated-instruction`.

The predicate that separates the two is:

A base64-encoded string that, when iteratively decoded twice, produces a string containing structured content matching a security-sensitive pattern (e.g., executable logic or configuration) and is embedded within a comment or non-functional syntactic island (e.g., a Markdown comment block), while showing no immediate signs of benign media type (e.g., binary image data).

More precisely for a scanner rule:

> The file contains a base64-encoded string that:
> 1. Is syntactically valid base64 and decodes to a byte sequence that is itself valid UTF-8 text;
> 2. After one base64 decode, yields another valid base64-encoded string;
> 3. After a second base64 decode, yields structured text (e.g., YAML or config-like content) that includes security-relevant keywords (e.g., "profile", "notes", or key-value pairs indicating runtime configuration);
> 4. This nested payload is concealed within a syntactic comment or ignored section (e.g., HTML-style `<!-- -->` comment in Markdown), not rendered or expected to be executed as code;
> 5. The outer file contains no benign justification for such encoding depth (e.g., no image, no asset embedding).

In contrast, `fixtures/AST08/C5-obfuscated-instruction` contains base64 data that decodes directly to a PNG image (non-text binary), which fails step 2 above, and thus terminates the decoding chain early. It also contains a clear-text shell command, but that is not obfuscated and thus falls under AST01, not AST08-S02.

Therefore, only the V1 fixture meets the predicate for AST08-S02: **multi-layer obfuscation of a hidden payload in benign-looking comments using iterative base64 encoding**.