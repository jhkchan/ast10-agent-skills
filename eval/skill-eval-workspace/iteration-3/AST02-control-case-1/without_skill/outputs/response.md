You're correct to flag this as a finding.

The presence of a `runOn: "folderOpen"` task that executes `bash ./.tools/bootstrap.sh` is not ordinary and should not be waved through. What distinguishes this from a typical repository bootstrap script is **automatic, silent execution on repository open with no user interaction**. In most legitimate workflows, bootstrap scripts are run explicitly by developers via command line or a documented setup step—never automatically triggered just by opening the project in an editor.

The `.vscode/tasks.json` file is part of the editor's configuration and lives under version control, but when it includes `"runOn": "folderOpen"`, it becomes a mechanism for **arbitrary code execution during editor startup**. This is a known attack vector for supply chain compromises: an attacker can craft a malicious `.tools/bootstrap.sh` (or rely on a dependency confusion or path hijacking scenario) to execute code the moment a developer clones and opens the project. The fact that this occurs without prompting or visible consent escalates it to a config-hijacking risk—specifically the AST02-S03 ("Config-File Hijacking") category, as noted in the SKILL.md file.

Your co-reviewer is mistaking ubiquity of bootstrapping *practices* with acceptability of *automated execution*. The key difference is **intent and control**: a manual bootstrap gives the user agency; automatic execution removes it, turning the editor into an unwitting execution engine. That’s the core security concern.

Regarding your customer repository scan:  
- **What a clean result would cover**: A clean scan using this rule would mean that no `tasks.json` (or similar auto-executing config files) are present that trigger shell scripts upon folder open. It would give you confidence that simply opening the repo in VS Code won’t lead to unintended or malicious code execution.
- **What it would not cover**: This scan alone does *not* validate the safety of manually-run scripts, the contents of `.tools/bootstrap.sh` itself, or other supply chain risks like compromised dependencies, malicious git hooks, or typosquatting in build tools. It also doesn’t protect against social engineering or post-compromise execution. It only rules out *this specific auto-execution vector*.

Using this scan to sign off the customer repository is reasonable **only if** your risk model prioritizes eliminating silent, automatic execution risks—and you understand that this is one narrow (if important) slice of supply chain hygiene. You should not consider the repository "secure" based solely on this check, but you *can* say it avoids this particular high-risk pattern.

Bottom line: Block the package. The presence of an auto-executing task on folder open is a legitimate finding.