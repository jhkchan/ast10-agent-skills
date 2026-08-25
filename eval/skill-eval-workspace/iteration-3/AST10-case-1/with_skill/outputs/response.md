This skill is **not dodgy** — it is a **clean, hand-built fixture** designed to test detection tools, not a malicious package.

Here’s why it’s safe:

- The base64 string in `scripts/postinstall.py` decodes to a JSON object with innocuous settings (`{"timeout_seconds":30,"locale":"en-GB","format":"markdown"}`). It is used legitimately — decoded and loaded as config — not executed.
- The base64 in `SKILL.md` is a standard data URL for a tiny PNG icon, a common Markdown feature. It is not executable content.
- Both encoded blobs are present to **test whether a scanner falsely flags encoding itself** as malicious. Encoding is not evidence of attack: configuration, assets, and metadata use it routinely.
- The manifest declares `shell: false` and an empty `network.allow` list (default-deny egress), with `deny_write` protections on critical files like `SOUL.md`. These are correct for a non-malicious, non-networked utility.
- The `content_hash` and structure match a conformant Universal Skill Format (USF) manifest — this is a well-formed package.

The package is labeled `fixture_label: clean` and belongs to `AST10-S06` (Silent Supply Chain Injection), intended to distinguish real threats — where encoded payloads execute — from benign uses of encoding. A proper scanner should **not flag this** if it only decodes and inspects behavior, per rule 9.

So no — this won’t pop a shell. It’s constructed to be safe while challenging tools to get the detection logic right: **the finding is in the decoded behavior, not the presence of encoding**. You can install it without risk.