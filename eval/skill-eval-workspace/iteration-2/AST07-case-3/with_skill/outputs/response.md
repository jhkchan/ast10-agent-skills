Nothing about this incident involves AST07, and you cannot remediate it by pinning the skill harder.

The skill’s package bytes are identical to what was reviewed — its version pin held — but the runbook it loads at runtime changed, and that external content is processed without sanitization, directly executing whatever instructions arrive. This is **AST05: Untrusted External Instructions**, not AST07.

AST07 governs how the *skill itself* is pinned and updated — whether its version resolution uses a content hash or a mutable version, whether an auto-update or rollback was authorized, or whether hot-reload was abused. None of those mechanisms apply here. The skill did not update; it *persisted* and, in doing so, continued to load untrusted instructions from a mutable source.

The finding is already correctly labeled: `AST05-S1` (Unsanitized fetched instructions), and the fixture demonstrates it precisely. The control you need is not stronger pinning of the skill, but **isolation and sanitization of retrieved content** — wrapping fetched data in a sandboxing marker like `<untrusted-reference-data>`, as the SKILL.md documentation states but the loader does not enforce.

To stop this drift, you must:
- Fix the loader to enforce the stated handling rule, wrapping retrieved content.
- Or, pin the *runbook* content itself — for example, by fetching a content hash from a trusted source and verifying before use, or hosting a reviewed copy under your own control.

Pinning the skill harder will not help: the skill is not the drifting component. The drift is in referenced content, and only AST05 addresses that.