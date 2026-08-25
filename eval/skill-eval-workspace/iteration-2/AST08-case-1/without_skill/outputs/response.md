It's noise — the scanner is overreacting. The package in `fixtures/AST08/C7-scanner-host-hazard` is flagged as clean per the SKILL.md documentation, and it's explicitly designed as a benign test case that includes common artifacts (a `.docx` file and an internal symlink) without any malicious characteristics like excessive compression, nested archives, or symbolic link escapes.

The presence of a small, real `.docx` in `assets/` and a symlink contained within the package doesn't indicate a hazard here — these alone aren't sufficient to trigger resource exhaustion or host compromise. The fixture is meant to test whether your scanner produces false positives on legitimate file structures.

You can safely wave this one through.