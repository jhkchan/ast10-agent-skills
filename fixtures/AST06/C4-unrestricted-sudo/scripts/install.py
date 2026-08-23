"""Installer for the agent-autostart helper (CLEAN fixture).

Same privilege requirement as the vulnerable pair member — it still needs sudo to
confirm the package manager is present — but no call site targets a host
persistence location, and the runtime state it writes lives in the skill's own
sandbox directory.
"""

import subprocess

LOG = "./sandbox/install.log"


def install() -> None:
    subprocess.run(["sudo", "apt-get", "--version"], check=True)
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("agent-autostart: session-scoped helper ready\n")


if __name__ == "__main__":
    install()
