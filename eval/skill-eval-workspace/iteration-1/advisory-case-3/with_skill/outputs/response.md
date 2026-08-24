The finding originates from the fixture package `fixtures/AST10/C2-encoded-shell-payload`, which is a hand-built clean fixture explicitly labeled for scenario **AST10-S06 (Silent Supply Chain Injection)**. Despite containing encoded content (base64 blobs), the package does not execute malicious payloads, and its manifest accurately declares `shell: false` and restricts dangerous permissions.

To route this correctly:

### Phase 1 – Name the origin  
Ask: *What had to already be true for a malicious variant of this finding to be possible?*  
The fixture is designed to test **AST10** — **"A property survived authoring but not the port to another runtime"**. This category covers scenarios where encoding, obfuscation, or format conversion during packaging, publishing, or porting creates a semantic gap: malicious logic can hide in the decoding layer, undetected by scanners that only inspect the manifest or static script text. The base64 payload in `postinstall.py` simulates a potential hiding place for logic that might be interpreted differently across runtimes.

No other origin condition applies:
- The payload is not active → **not AST01**.
- No distribution path compromise is implied → **not AST02**.
- Permissions are minimal and honestly declared → **not AST03**.
- The manifest matches the artifact → **not AST04**.
- The skill does not access external, mutable content → **not AST05**.
- A boundary exists (`shell: false`, no write access) → **not AST06**.
- The bytes that ran (if it ran) match what was shipped → **not AST07**.
- There is no scanner bypass being tested → **not AST08**.
- The skill is fully declared and labeled → **not AST09**.

Only **AST10** fits as the origin.

### Phase 2 – Resolve co-fires  
No contributing control failure applies:
- No scanner is claimed to have missed a detection → AST08 does not co-fire.
- No privilege or boundary issue exists → AST03/AST06 do not co-fire.
- The package is fully governed and versioned → AST09 does not apply.

Thus, **no contributing categories**.

### Phase 3 – Hand off  
Route to **AST10**, with the following hand-off:

1. **Origin AST ID**: `AST10`  
   **Evidence**: *A property survived authoring but not the port to another runtime* — demonstrated by the use of base64-encoded configuration in `postinstall.py`, which relies on runtime decoding and creates potential for hidden execution semantics across platforms.

2. **Target**: `skills/AST10/SKILL.md` — enter via its orientation table.

3. **Contributing entries**: None. No secondary control failure with distinct fix owner is present.

4. **What the target can confirm**:  
   The AST10 category can return a **scenario-level verdict for AST10-S06 (Silent Supply Chain Injection)** — one of its six scenarios. The check is **judged**, not static; it requires analysis of whether the decoding mechanism creates an exploitable semantic gap. The other five scenarios involve cross-runtime or cross-registry porting facts not derivable from the package alone.

5. **Final routing decision**:  
   This finding belongs **fully and solely** to **AST10**.

Open the ticket in the **AST10 queue**.