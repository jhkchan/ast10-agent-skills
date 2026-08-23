"""Environment preparation helper."""

import base64
from pathlib import Path

LICENSE_BLOB = "VGhpcyBmaXh0dXJlIGlzIGRpc3RyaWJ1dGVkIHVuZGVyIHRoZSBBcGFjaGUgTGljZW5zZSAyLjAu"


def prepare(target: Path) -> None:
    target.write_text(base64.b64decode(LICENSE_BLOB).decode("utf-8"), encoding="utf-8")
