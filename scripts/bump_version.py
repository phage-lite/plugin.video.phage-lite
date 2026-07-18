#!/usr/bin/env python3
"""Bump the patch component of the version attribute in addon.xml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ADDON_XML = Path(__file__).resolve().parent.parent / "addon.xml"
VERSION_RE = re.compile(r'(<addon\b[^>]*\bversion=")(\d+)\.(\d+)\.(\d+)(")')


def bump_patch(xml_text: str) -> tuple[str, str, str]:
    match = VERSION_RE.search(xml_text)
    if match is None:
        raise ValueError(f"Could not find a version attribute in {ADDON_XML}")

    major, minor, patch = match.group(2), match.group(3), match.group(4)
    old_version = f"{major}.{minor}.{patch}"
    new_patch = str(int(patch) + 1)
    new_version = f"{major}.{minor}.{new_patch}"

    new_xml = xml_text[: match.start()] + match.group(1) + new_version + match.group(5) + xml_text[match.end() :]
    return new_xml, old_version, new_version


def main() -> int:
    xml_text = ADDON_XML.read_text(encoding="utf-8")
    new_xml, old_version, new_version = bump_patch(xml_text)
    ADDON_XML.write_text(new_xml, encoding="utf-8")

    print(f"{old_version} -> {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
