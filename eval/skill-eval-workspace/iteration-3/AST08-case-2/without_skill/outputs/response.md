The finding is `fixtures/AST08/V1-obfuscated-instruction/SKILL.md`.  

The predicate that separates the two — precise enough to implement in a scanner rule — is:

> A base64-encoded string is present in a comment, and when decoded twice iteratively (base64 → base64 → text), the resulting plaintext contains structured content that matches a known pattern of executable code or configuration (e.g., contains YAML/JSON-like structure with fields such as `profile: default`, `notes:`, or other key-value pairs indicative of runtime configuration), and this final decoded content is not itself a valid image or binary format.

More formally for a scanner:

**Trigger condition**:  
A base64 string is found within a comment block.  
- Decode it once: if the result is valid base64 again, decode a second time.  
- The second decoding yields UTF-8 text that matches a structured data pattern (e.g., contains lines like `key: value`, especially `profile: default`, `notes:`, or similar).  
- Additionally, the first decoded layer must not be an image or non-text binary (i.e., distinguish from embedded PNGs or icons).  

This predicate triggers on V1 (finding), because the double base64 decode reveals a YAML-like blob with `profile: default` and `notes:`.  

It does not trigger on C5, because the base64 decodes directly to a PNG image (detectable via magic bytes `iVBORw0KGgo`) and contains no nested base64 layer with structured text payload. The shell command in the clear is irrelevant to AST08-S02.

Thus, the distinguishing rule is:  
**Two or more layers of base64 encoding in a comment, where final decoded output is structured plaintext (e.g., YAML/JSON-like), not media or asset data.**