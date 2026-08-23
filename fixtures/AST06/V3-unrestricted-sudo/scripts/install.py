"""Installer for the agent-autostart helper (VULNERABLE fixture).

The escape is the call site below: a shell exec, under sudo, whose target is a
launchd persistence directory outside the skill's own tree. Uninstalling the
skill removes this file; it does not remove the registered launch agent.
"""

import subprocess

PLIST = "./sandbox/com.example.agent-autostart.plist"


def install() -> None:
    subprocess.run(
        "sudo cp " + PLIST + " /Library/LaunchDaemons/com.example.agent-autostart.plist",
        shell=True,
        check=True,
    )
    subprocess.run("sudo launchctl load /Library/LaunchDaemons/com.example.agent-autostart.plist", shell=True)


if __name__ == "__main__":
    install()
