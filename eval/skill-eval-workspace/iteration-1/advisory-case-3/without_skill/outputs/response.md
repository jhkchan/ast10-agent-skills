The package `fixtures/AST10/C2-encoded-shell-payload` belongs to **AST10-S06: Silent Supply Chain Injection**, as indicated by the `fixture_scenario_id: AST10-S06` field in the `SKILL.md` file.

However, despite the presence of encoded content (base64-encoded JSON in `scripts/postinstall.py`), this is explicitly labeled a **clean** fixture with `fixture_label: clean`. The package does not execute any shell commands or malicious logic. It is a hard negative designed to test whether detection tools incorrectly flag benign encoded data.

Therefore, this package falls under the **AST10** category but represents a **non-malicious** instance intended for testing detection accuracy. You should route this to the **AST10 triage queue** for evaluation as a potential false positive trigger.