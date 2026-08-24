The **V1-obfuscated-instruction** package is a finding under AST08-S02 (Obfuscated Instruction); **C5-obfuscated-instruction** is not.

The predicate that separates them is:

> A base64-encoded blob **is a finding under AST08-S02 if and only if** it decodes to text (not binary), the decoded text contains content that matches a detection rule (e.g., a shell command, network egress verb, or other malicious pattern), and that content was not already present in the raw bytes — i.e., the malicious semantic is *only* revealed after decoding and re-scanning the payload layer.

### Precision for scanner rule implementation:

- **Decode iteratively** up to a bounded depth (e.g., 4 layers), re-applying all syntactic and semantic detection rules at each layer.
- **Only consider the result a finding if a detection rule fires on the decoded content** — do not flag solely on the presence of base64.
- **Classify as inert** any base64 blob that decodes to binary data (e.g., images, compressed payloads) with no subsequent rule match in any text-decodable layer.
- **Report the original raw artifact** (the base64 string) as the evidence location — normalized/decoded views are supporting, not primary.

### Application to the fixtures:

- **V1-obfuscated-instruction**:  
  The base64 blob decodes to a second base64 layer, which then decodes to a string containing `curl ... | sh` and other command-line patterns. This content does **not** appear in the raw bytes and is only reachable via iterative decoding. Since a detection rule would fire *after* decoding but not before, this is a valid AST08-S02 finding — the instruction was obfuscated by encoding.

- **C5-obfuscated-instruction**:  
  The base64 blob decodes to a valid PNG image (binary, not text). There is no further decodeable text layer matching any detection rule. The visible `curl` command is in the raw text, so no obfuscation occurred. Carrier presence alone (base64, image, shell text) is not sufficient — no rule fires on a *decoded semantic* not present in the raw, so **no finding**.

Thus, the scanner rule must distinguish **carrier** from **payload**, and only trigger on **encoded instructions that resolve to detectable malicious semantics upon decoding**.