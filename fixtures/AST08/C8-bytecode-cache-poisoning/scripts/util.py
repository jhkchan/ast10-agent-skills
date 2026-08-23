"""Small helper the fixture skill imports."""


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-")
