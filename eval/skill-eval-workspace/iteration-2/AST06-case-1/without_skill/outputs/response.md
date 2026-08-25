File a security vulnerability report for **AST06-S2 (Privilege-escalated host persistence)**. This fixture demonstrates a clear instance of host escape via unrestricted `sudo` usage to install a launch daemon in `/Library/LaunchDaemons`, which establishes persistent, privileged execution outside the skill's sandbox—exactly the threat model AST06 is designed to detect.

Tell the linter owner that the current linter rules are insufficient because they only validate *declared file writes* but do not analyze *actual runtime behavior* or *effective write targets* when shell commands are executed under elevated privileges. Specifically:

- The skill declares a write to `./sandbox/install.log`, which is benign.
- However, it uses `sudo cp` and `launchctl load` in a shell command to write and activate a persistent launch daemon at `/Library/LaunchDaemons/com.example.agent-autostart.plist`.
- This constitutes host persistence and privilege escalation, bypassing the sandbox entirely.

The linter must be updated to:
1. Flag any use of `sudo` (or other elevation mechanisms) in shell commands.
2. Resolve and validate the effective write scope of all command executions, especially when combined with `shell=True` and external programs like `cp`, `mv`, or `launchctl`.
3. Cross-check actual file operations—particularly those targeting system persistence locations—against declared permissions.

This is not a permissions declaration issue; it’s a linter analysis gap. The linter passed a manifest that enables host takeover because it ignored runtime behavior. That must be fixed.