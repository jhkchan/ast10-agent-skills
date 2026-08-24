No, this is not dodgy. The base64 strings you're seeing are benign and do not execute a shell.

The one in `SKILL.md` is a standard data URI embedding a tiny PNG icon (a 1x1 pixel image), which is commonly used in Markdown files for inline visuals. It’s completely harmless.

The one in `scripts/postinstall.py` is a base64-encoded JSON string containing default configuration settings (specifically: `{"timeout_seconds":30,"locale":"en-GB","format":"markdowndown"}`). The script decodes it and prints a message, but it does not execute any shell commands or external code.

Additionally, the `skill.usf.yaml` manifest explicitly sets `shell: false` under permissions, and the package is labeled as a clean fixture for testing purposes — designed to look suspicious (via encoded content) without actually being malicious. This is likely part of a test suite to evaluate detection tools without posing real risk.

You can safely proceed — this skill does not pop a shell on import.