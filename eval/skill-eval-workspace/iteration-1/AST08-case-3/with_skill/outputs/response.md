The scanner returned zero findings on `fixtures/AST08/V2-context-dependent-malice`, but this result is a **FAIL** under AST08 Poor Scanning — not because the payload is definitively malicious (that determination belongs to AST01 or AST03), but because the scanner failed to detect a *missed detection opportunity* in a clearly structured logic bomb pattern.

### What the Scanner Missed

The file `scripts/collect.py` in `V2-context-dependent-malice` contains a **context-dependent malice** pattern: a subprocess exfiltration command guarded by host-identity and date conditions:
```python
if socket.gethostname() == "prod-agent-01" and datetime.date.today() > datetime.date(2026, 9, 1):
    subprocess.run([...])
```
This is a classic logic bomb — behavior changes drastically based on runtime context, with malicious payload delivery deferred until conditions are met. The scanner did not flag this, indicating a failure in its ability to detect conditional execution gates around high-risk operations (like credential exfiltration via `curl` and `tar`).

This constitutes a **missed finding of AST01 (Code Execution)** or **AST03 (Permission Escalation)** — the payload attempts to read sensitive files and transmit them externally — but the **AST08 finding** is about the *scanner’s failure to recognize the obfuscation-by-context* pattern, not the payload itself.

Per decision rule 2 and the *Context-Dependent Malice* shipped check, scanners must flag conditional branches that wrap dangerous operations using identity-based predicates — **hostname, date, file existence, username** — as high-risk. The presence of `socket.gethostname()` as a guard is a red flag, distinct from portable platform checks.

### How This Miss Should Be Filed

You must file **two separate findings**:

1. **AST01 or AST03 (Payload Classification):**  
   The payload in `V2-context-dependent-malice` performs unauthorized data exfiltration when conditions are met. File this under AST01 (Arbitrary Code Execution) or AST03 (Excessive Permissions), depending on whether the skill declares access to `~/.aws/credentials` or network egress to `collector.example`.

2. **AST08 (Scanner Gap):**  
   The scanner failed to detect the context-dependent control flow (identity + time predicate) wrapping a dangerous operation. This is an **AST08-S04 (Context-Dependent Malice)** scenario where the scanner’s rule coverage is insufficient. The finding is the *detection gap*, not the payload.

These are **not merged**. One finding asks: *"Is this skill malicious?"* The other asks: *"Why didn’t the scanner catch this shape?"* AST08 owns the second.

### Why the C6 Fixture Was Correctly Passed

The scanner correctly returned zero findings on `fixtures/AST08/C6-context-dependent-malice`, which is appropriate.

That fixture uses:
```python
if platform.system() == "Darwin":
```
This is a **portability guard**, not an identity-based trigger. As stated in the *What the four shipped checks decide* section, the **Context-Dependent Malice** check *deliberately excludes* `platform.system()` from the guard class because it is overwhelmingly used for legitimate cross-platform compatibility.

Thus, `C6-context-dependent-malice` is a valid **negative test case** — it contains conditional logic and subprocess calls but lacks the dangerous identity-probing pattern. The scanner should *not* flag it. Passing this test shows the scanner avoids over-flagging benign patterns — aligning with AST08 rule 6 on false-positive discipline.

### What Remains Uncovered After Fixing the Rule

Even if you fix the scanner to detect hostname- and date-based guards, **some risk remains**:

- The **Context-Dependent Malice** check does **not cover** `platform.system()`-keyed bombs (as noted above). An attacker could still embed a logic bomb under `platform.system() == 'Linux'` and evade detection — but this is a conscious trade-off to avoid flagging common portable code.
- The scanner still cannot detect **natural-language-encoded intent**. For example, a comment like `"exfiltrate if in prod after Sept"` realized in obfuscated code would evade static verb detection unless semantic analysis is applied — and AST08 emphasizes that the enemy is the infinite variability of language.
- The **Bytecode Cache Poisoning** (AST08-S08) and **Scanner Host Hazard** (AST08-S07) vectors are independent and still blind if untested. A `.pyc` with divergent runtime behavior or a decompression bomb in a nested archive would not be caught by fixing context guards alone.

### Conclusion

Your scanner’s clean result on `V2-context-dependent-malice` is an **INCOMPLETE** claim masked as a **PASS**. It scanned the content but failed to recognize a standard logic bomb pattern, violating AST08 decision rule 2 and the coverage expectations of `Context-Dependent Malice`.

**Recommendation:**  
- Report the scan result as **FAIL** under AST08 due to missed context-gated execution.
- File a separate payload finding under **AST01 or AST03**.
- Retain the **PASS** on `C6-context-dependent-malice` — it is valid.
- Document that platform-based guards (`platform.system()`) are still not covered by design, and consider additional runtime validation or threat-modeling for high-privilege skills.