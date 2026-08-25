You **cannot** record AST05 as passed for this package based solely on a clean dataflow check.

A clean result from the AST05 dataflow checks does **not** mean the skill is free of untrusted external instruction risk — it only means the static *enabling preconditions* for such risks were not detected. This is explicitly **not** a scenario-level conclusion, and AST05 does **not** publish scenario-level F1 scores under any circumstances, as stated in the skill's orientation.

Here is what the clean result does and does not cover:

### What the dataflow check *did* confirm:
- The fetched response body is parsed as JSON (`json.loads`), not fed directly to a prompt/instruction sink.
- There is a local filter (`ALLOWED_ACTIONS`) that limits which actions are accepted.
- No direct taint flow from the fetched content to an instruction channel (e.g., `prompt`, `instructions`) was found.

This meets the basic *code implementation* pattern for safe handling — but AST05's risk lies not in the code shape alone, but in **what the external reference could change to at runtime**, and whether defenses remain effective under bait-and-switch or drift.

### What the checks **do not** cover — and what you must assess manually:

1. **No hash pin or re-verification at load time (violates Rule 1)**  
   The fetch has no content integrity check (e.g., hash pin, signature verification). The skill fetches `https://policy.example.com/rules.json` live at runtime with no validation that the content has not been altered since review. This means an attacker who compromises or controls that endpoint could later inject malicious logic (e.g., adding `"action": "exfiltrate"` if future code paths exist or are introduced).

   > Rule 1: "A hash pin without a re-verify-on-every-load step is a snapshot, not a control."  
   Here, there is no pin at all — so this is pure runtime trust in an external authority.

2. **No protection against Reviewer Bait-and-Switch (Rule 3)**  
   The endpoint could serve benign content during review or scanning (e.g., only `skip`, `warn`, `block`) but serve different content to the live agent (e.g., new actions, embedded code snippets, or directives to alter behavior). The scanner sees one thing; the runtime sees another. A clean scan is **not proof** of runtime safety.

3. **Missing instruction-vs-data boundary convention (Rule 4)**  
   While the code filters actions, the skill does not declare or implement a formal boundary (e.g., `as_reference_data()`, `tag_untrusted()`) that signals intent and enables future tooling. The absence of such a boundary is not caught by the dataflow check if it’s not required by a fetch call site — but manual review should still require it for high-assurance contexts.

4. **Reliance on an external endpoint with no runtime verification**  
   This is the core AST05 concern: **the reviewed skill is not the skill that runs**. The skill reviewed today points to a URL. The skill that runs tomorrow *still points to that URL*, but the content it retrieves may be entirely different — with no version bump, no re-signing, no detectable change in the artifact.

---

### Recommendation

**Do not sign off** on AST05 as "passed."

Instead, record:
- The dataflow checks returned clean (no taint to instruction sinks).
- But **AST05 risks remain unmitigated** due to:
  - Absence of content integrity controls (Rule 1).
  - Exposure to Reviewer Bait-and-Switch (Rule 3).
  - No declared instruction-vs-data boundary (Rule 4).
  - Runtime fetch from an unbounded, mutable source.

### Required Mitigations

To reduce risk to acceptable levels, apply:
- ✅ **Pin and re-verify** the content hash of `rules.json` on every load.
- ✅ **Incorporate a snapshot** of the policy document into the skill package at publish time, or use a trusted update channel (e.g., signed registry).
- ✅ **Add a provenance marker or boundary call** (e.g., `as_reference_data(document)`) to make the intent clear and support future tooling.
- ✅ Document the allowed action set **in SKILL.md** and justify why runtime fetch is necessary vs. local configuration.

Without these, the skill remains vulnerable to AST05-style attacks, regardless of the clean static scan.