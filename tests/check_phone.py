#!/usr/bin/env python3
"""The public site publishes one SHOR Foundation phone number.

Visible text is +91 80901 08939, tel: links are tel:+918090108939,
WhatsApp links use 918090108939, and schema.org telephone is
+91-8090108939. No other phone-like number may remain on the pages.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OFFICIAL_DIGITS = "8090108939"
OFFICIAL_TEL = "tel:+918090108939"
OFFICIAL_DISPLAY = "+91 80901 08939"
OFFICIAL_SCHEMA = "+91-8090108939"
OFFICIAL_WA_DIGITS = "918090108939"

CONTENT_SUFFIXES = {".html", ".js", ".json", ".xml", ".txt", ".md"}
SKIP_DIRS = {"fonts", "images", "products", "solutions-img", "css", "tests", ".git"}

# Phone-shaped tokens. Longer digit runs (account numbers, photo ids) and
# identifiers that are not phones (IFSC, PAN, CIN, Darpan, URNs, UPI, dates)
# do not match these patterns.
PHONE_RE = re.compile(
    r"""
    tel:[+\d][\d\-\s]*
    | (?:https?://)?(?:wa\.me/|api\.whatsapp\.com/send\?phone=)\d+
    | "telephone"\s*:\s*"[^"]*"
    | \+91[\s\-]*(?:\d[\s\-]*){10}
    | (?<!\d)0[6-9](?:[\s\-]?\d){9}(?!\d)
    | (?<!\d)[6-9]\d{4}[\s\-]\d{5}(?!\d)
    | (?<!\d)[6-9]\d{9}(?!\d)
    | TEL[;:][^\s<]+
    """,
    re.IGNORECASE | re.VERBOSE,
)
TEL_HREF_RE = re.compile(r'href="(tel:[^"]*)"')
ANCHOR_RE = re.compile(r'<a\s+href="(tel:[^"]*)">([^<]*)</a>')
WA_RE = re.compile(
    r'https?://(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d+)',
    re.IGNORECASE,
)
SCHEMA_RE = re.compile(r'"telephone"\s*:\s*"([^"]*)"')


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def content_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in CONTENT_SUFFIXES or path.name == "vercel.json":
            files.append(path)
    return files


def digits_of(value: str) -> str:
    return re.sub(r"\D", "", value)


def is_official(value: str) -> bool:
    digits = digits_of(value)
    return digits in {OFFICIAL_DIGITS, "91" + OFFICIAL_DIGITS}


def check(errors: list[str]) -> None:
    pages = content_files()
    html_pages = [path for path in pages if path.suffix.lower() == ".html"]
    if not html_pages:
        fail(errors, "no html pages found")
        return

    for path in pages:
        text = path.read_text()
        rel = path.relative_to(ROOT)
        for match in PHONE_RE.finditer(text):
            token = match.group(0)
            if not is_official(token):
                line = text.count("\n", 0, match.start()) + 1
                fail(errors, f"{rel}:{line} has a non-official phone-like value {token!r}")

        for href in TEL_HREF_RE.findall(text):
            if href != OFFICIAL_TEL:
                fail(errors, f"{rel} tel link is {href!r}, expected {OFFICIAL_TEL}")

        for href, label in ANCHOR_RE.findall(text):
            if href == OFFICIAL_TEL and label != OFFICIAL_DISPLAY:
                fail(errors, f"{rel} tel link text is {label!r}, expected {OFFICIAL_DISPLAY}")

        for wa_digits in WA_RE.findall(text):
            if wa_digits != OFFICIAL_WA_DIGITS:
                fail(errors, f"{rel} WhatsApp link uses {wa_digits}, expected {OFFICIAL_WA_DIGITS}")

        for telephone in SCHEMA_RE.findall(text):
            if telephone != OFFICIAL_SCHEMA:
                fail(errors, f"{rel} schema telephone is {telephone!r}, expected {OFFICIAL_SCHEMA}")

        if path.suffix.lower() == ".html":
            display = text.count(OFFICIAL_DISPLAY)
            hrefs = text.count(f'href="{OFFICIAL_TEL}"')
            if display == 0 or hrefs == 0:
                fail(errors, f"{rel} is missing the official phone {OFFICIAL_DISPLAY}")
            if display != hrefs:
                fail(errors, f"{rel} shows the official phone {display} times but links it {hrefs} times")
            if "9599154905" in digits_of(text) or "8099010839" in digits_of(text):
                fail(errors, f"{rel} still contains a retired SHOR phone number")


def main() -> None:
    errors: list[str] = []
    check(errors)
    if errors:
        print(f"{len(errors)} phone check(s) failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"phone checks passed ({len(content_files())} files)")


if __name__ == "__main__":
    main()
