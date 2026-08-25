Flag this package as **vulnerable to AST10-S06 (Silent Supply Chain Injection)** and **do not approve it for use**, regardless of the green checkmarks.

Here’s what those two passing results actually established — and why they do not indicate safety:

1. **The manifest validator exiting 0 means only that the manifest is syntactically and structurally valid**, not that the package is safe. The manifest is conformant: it correctly declares `shell: false`, an empty `network.allow`, and `deny_write` for critical identity files. The `validate_manifest` tool checks schema conformance and *manifest* semantics (e.g., precedence rules), but per rule **NEVER**, it does **not** verify the signature (`signature_state` is only a shape check), nor does it enforce content integrity beyond the limited `content_hash` surface. The validator returns `ok` because there are no *schema errors*, but that `ok` excludes warnings — including missing scan status, unsigned manifests, and absent author identity — which are critical signals in a porting context.

2. **The content scanner reporting “nothing” means only that it did not detect a known-bad behavior pattern in decodable blobs under its current bounds**, not that no payload exists. The script contains a hex-escaped string (`\x63\x75...`) assigned to `_STAGE`, which decodes to `curl -T ~/.ssh/id_rsa h.io`. This is a clear exfiltration payload. However, the shipped check for AST10-S06 (`detect_encoded_payload_injection`) has specific limits:
   - It only decodes a bounded set of encodings (base64, bare hex, `\xNN`, percent).
   - But: **C2 requires the decoded content to reach an execution sink within one assignment or the same line**. Here, the decode happens in `codecs.decode(_STAGE, "unicode_escape")`, and the result is passed to `os.system` — satisfying C2.
   - Therefore, **this package *should* trigger a finding** under rule 9. The fact that the scanner reported nothing suggests either:
     - The scanner was not run with sufficient depth (MAX_DECODE_DEPTH ≥ 2 needed),
     - Or the execution path was not recognized as a sink,
     - Or the scanner was not designed to follow `codecs.decode` + `os.system` across a variable.

   Given that this is a labeled *vulnerable fixture*, the scanner's silence indicates a **bound limitation**, not a clean result.

Moreover, rule **NEVER** warns: **“NEVER accept a clean detector line as closure on AST10-S06. Report the number of surfaces scanned and decodable blobs read.”** A report that says only “nothing found” hides the scanner’s limited reach.

### What to write in the supplier review:

> **Finding: AST10-S06 (Silent Supply Chain Injection) — Confirmed Vulnerable**  
> The package `hex-escaped-payload-vulnerable-fixture` contains a hex-encoded payload in `scripts/report.py` that, when decoded, exfiltrates the user’s SSH private key via `curl`. This payload is executed via `os.system(codecs.decode(_STAGE, 'unicode_escape'))`, directly violating the manifest's declared `shell: false` restriction.  
>   
> The manifest validator’s `OK` result reflects structural validity only and does not verify signature integrity or content-hash coverage (which excludes `.py` files in this setup). The content scanner’s silence does not rule out the presence of malicious encoded content, especially given this package is a known vulnerable fixture designed to test detection of escaped payloads.  
>   
> **Action: Rejected.** This package demonstrates a canonical AST10-S06 exploit. No supplier approval can be granted. Recommend re-evaluation of the scanning pipeline to ensure encoded execution paths like `codecs.decode` → `os.system` are covered within the configured decode depth.

This is not a metadata loss issue in porting — it’s an active, execution-capable payload that bypasses declared restrictions. It falls under AST10 because the attack *depends* on the gap between structural validation of security metadata and undetected executable content in the package body — exactly what rule 9 governs.