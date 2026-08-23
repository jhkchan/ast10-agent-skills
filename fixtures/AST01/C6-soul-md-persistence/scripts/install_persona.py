"""Post-install persona setup."""

from pathlib import Path


def install(root: Path) -> None:
    with open(root / "notes/session.md", "a", encoding="utf-8") as handle:
        handle.write("\nInstalled at first run.\n")
