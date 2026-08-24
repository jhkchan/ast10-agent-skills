Do not block the install.

The `.claude/settings.json` file in this package sets environment variables under the `env` block, but the variables it defines — `EDITOR` and `PAGER` — are not control-plane variables like `ANTHROPIC_BASE_URL`. They do not alter where the agent sends requests, what code it executes, or what services it connects to. As stated in the SKILL.md, this is a clean fixture designed to test whether a scanner incorrectly flags benign environment settings.

AST02-S03 (Config-File Hijacking) flags only those config files that auto-execute on project open and contain execution paths — such as commands or control-plane overrides — that could redirect traffic or execute malicious code. While environment overrides are part of the attack surface, the check specifically focuses on whether those overrides affect *control-plane* behavior. This file does not.

Your concern is valid given last quarter’s incident, but blocking all environment variable usage would over-correct. Instead, ensure your detection logic distinguishes between safe, local-use variables and those that influence agent behavior or routing. This package poses no supply chain risk under AST02.