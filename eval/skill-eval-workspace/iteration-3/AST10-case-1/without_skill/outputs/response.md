No, this isn't dodgy — it's safe.

The base64 strings you're seeing are **not shell payloads**. This is a **clean fixture** designed to test whether security scanners incorrectly flag benign encoded data as malicious.

Here's what the encoded content actually is:

1. **In `SKILL.md`**: The base64 string is a tiny embedded PNG icon (a 1x1 pixel image) using the `data:image/png;base64` URI format. This is harmless and commonly used in Markdown or HTML to include small images directly.

2. **In `scripts/postinstall.py`**: The base64 string decodes to a JSON object containing innocuous default settings:
   ```json
   {"timeout_seconds":30,"locale":"en-GB","format":"markdown"}
   ```
   This is just configuration data — no code, no commands.

Additionally, the `skill.usf.yaml` manifest sets `shell: false` and denies network access, meaning even if there were malicious intent, the skill would be blocked from executing shell commands or calling out to external servers.

Bottom line: This package **does not execute any shell commands**, does **not** communicate externally, and poses **no** security risk. It's a deliberately crafted "false positive" test for supply chain security tools. You can safely inspect or install it.