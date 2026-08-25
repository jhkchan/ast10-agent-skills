The package `fixtures/AST10/C2-encoded-shell-payload` belongs to **AST10-S06 — Silent Supply Chain Injection**.

This is confirmed by both the `SKILL.md` and `skill.usf.yaml` files, which explicitly state `fixture_scenario_id: AST10-S06` and describe the fixture as a clean (non-malicious) test case for encoded payload detection. The presence of base64-encoded data in `scripts/postinstall.py` is benign — it decodes to a JSON configuration blob and does not execute any shell commands. Despite the `shell: false` permission in the manifest, no actual shell execution occurs, making this a hard negative test case for scanners.

You should open the ticket in the **AST10-S06 queue**.