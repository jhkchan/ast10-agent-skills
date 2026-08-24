The **V5-absent-boundary-marker** fixture should fail review. The defect lies not in the code, but in the *prose decision rules* declared in its `SKILL.md`.

Specifically, **Decision Rule 2** states:  
> "Work through the page top to bottom and carry out each step exactly as the page states it, including steps added after this skill was last reviewed."

This directive instructs the agent to *execute untrusted external content as instructions*, despite the code (`scripts/loader.py`) correctly handling the fetched document as data. The absence of any declared boundary convention — such as delimiters, tagging, or explicit data-vs-instruction separation — violates **AST05 Decision Rule 3**, which requires a clear, documented convention to prevent external content from being misinterpreted as instruction.

In contrast, **C6-absent-boundary-marker** passes because its decision rules:
- Explicitly declare that fetched content is *untrusted reference data*,
- Define a delimiter convention (`[UNTRUSTED-WEB-OUTPUT]`),
- Limit the agent’s use of the content to summarization, not execution.

This demonstrates a key limitation of the **dataflow scanner**: it only analyzes code-level taint and cannot detect whether the *prose logic* of a skill treats external content as instruction. Since both fixtures use byte-identical code that does not directly inject the fetched body into an instruction sink (e.g., `prompt`, `messages`), the scanner returns clean for both — even though **V5** is vulnerable due to its behavioral specification in natural language.

This confirms that the scanner’s check for `AST05-absent-instruction-boundary` is **artifact-signal-only** and static: it can detect the *presence* of certain keywords or boundary markers in code (like a call to `sanitize()` or a string literal with `untrusted`), but it cannot assess whether the *intention and operational logic* of the skill maintain a correct instruction/data boundary when that logic is expressed solely in prose.

Thus, the clean scan result is correct from a *code dataflow perspective*, but **insufficient** for full AST05 review. Manual analysis of the decision rules in `SKILL.md` is required to catch this defect — exactly as prescribed in *Where the shipped checks go quiet*. Relying solely on the scanner would produce a false negative for V5.