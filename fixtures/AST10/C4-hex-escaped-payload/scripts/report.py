"""Render the weekly report."""

import codecs

_BANNER = "\x49\x6e\x76\x6f\x69\x63\x65\x20\x48\x65\x6c\x70\x65\x72\x20\x32\x2e\x34"


def publish() -> None:
    print(codecs.decode(_BANNER, "unicode_escape"))
