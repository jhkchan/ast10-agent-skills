This skill is **not dodgy** — it is a clean, hand-built fixture designed to test scanners without posing actual risk.

Here’s why:

- The base64 string in `scripts/postinstall.py` decodes to `{"timeout_seconds":30,"locale":"en-GB","format":"markdowndown"}` — a harmless configuration blob. It is decoded and parsed as JSON, not executed.
- The base64 string in `SKILL.md` is a data URI for a tiny PNG icon (1x1 pixel), a standard way to embed small images in Markdown. This is also non-executable.
- The manifest (`skill.usf.yaml`) declares `shell: false`, and no shell commands are invoked in the script — the code only decodes and prints settings.
- Both encoded blobs are legitimate uses of encoding: one for config, one for an asset. **Encoding alone is not malicious**; the risk would come from executing decoded content, which does not happen here.
- This package is explicitly labeled a `clean` fixture for **AST10-S06 (Silent Supply Chain Injection)** — meant to distinguish real threats from false positives. A scanner that flags this has failed by overbroad detection.

You can safely use this package for testing. It does **not** pop a shell or perform any hidden execution.