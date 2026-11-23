#!/usr/bin/env python3
"""The public site publishes exactly two SHOR Foundation phone numbers.

+91 80901 08939 (tel:+918090108939) comes first.
+91 95991 54905 (tel:+919599154905) comes second wherever both appear.
Any other phone-like number, including +91-8099010839, fails.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRIMARY_DIGITS = "8090108939"
SECOND_DIGITS = "9599154905"
PRIMARY_TEL = "tel:+918090108939"
SECOND_TEL = "tel:+919599154905"
PRIMARY_DISPLAY = "+91 80901 08939"
SECOND_DISPLAY = "+91 95991 54905"
PAIR = (
    f'<a href="{PRIMARY_TEL}">{PRIMARY_DISPLAY}</a>'
    f' · <a href="{SECOND_TEL}">{SECOND_DISPLAY}</a>'
)
ALLOWED_TELS = {
    PRIMARY_TEL: PRIMARY_DISPLAY,
    SECOND_TEL: SECOND_DISPLAY,
}
ALLOWED_DIGITS = {
    PRIMARY_DIGITS,
    "91" + PRIMARY_DIGITS,
    SECOND_DIGITS,
    "91" + SECOND_DIGITS,
}
ALLOWED_SCHEMA = {"+91-8090108939", "+91-9599154905"}
ALLOWED_WA = {"918090108939", "919599154905"}

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
MISMATCH = "+91-8099010839"


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


def is_allowed(value: str) -> bool:
    return digits_of(value) in ALLOWED_DIGITS


def check(errors: list[str]) -> None:
    pages = content_files()
    html_pages = [path for path in pages if path.suffix.lower() == ".html"]
    if not html_pages:
        fail(errors, "no html pages found")
        return

    for path in pages:
        text = path.read_text()
        rel = path.relative_to(ROOT)
        if MISMATCH in text:
            fail(errors, f"{rel} still has the mismatched phone number {MISMATCH}")

        for match in PHONE_RE.finditer(text):
            token = match.group(0)
            if not is_allowed(token):
                line = text.count("\n", 0, match.start()) + 1
                fail(errors, f"{rel}:{line} has a phone-like value other than the two SHOR numbers: {token!r}")

        for href in TEL_HREF_RE.findall(text):
            if href not in ALLOWED_TELS:
                fail(errors, f"{rel} tel link is {href!r}")

        for href, label in ANCHOR_RE.findall(text):
            expected = ALLOWED_TELS.get(href)
            if expected is not None and label != expected:
                fail(errors, f"{rel} tel link text for {href} is {label!r}, expected {expected}")

        for wa_digits in WA_RE.findall(text):
            if wa_digits not in ALLOWED_WA:
                fail(errors, f"{rel} WhatsApp link uses {wa_digits}")

        for telephone in SCHEMA_RE.findall(text):
            if telephone not in ALLOWED_SCHEMA:
                fail(errors, f"{rel} schema telephone is {telephone!r}")

        if path.suffix.lower() != ".html":
            continue

        for number, href in (
            (PRIMARY_DISPLAY, f'href="{PRIMARY_TEL}"'),
            (SECOND_DISPLAY, f'href="{SECOND_TEL}"'),
        ):
            if text.count(number) != text.count(href):
                fail(errors, f"{rel} phone link count for {number} does not match")

        first = text.find(PRIMARY_DIGITS)
        second = text.find(SECOND_DIGITS)
        if first != -1 and second != -1 and first > second:
            fail(errors, f"{rel} lists {SECOND_DIGITS} before {PRIMARY_DIGITS}")
        for line_no, line in enumerate(text.splitlines(), 1):
            line_first = line.find(PRIMARY_DIGITS)
            line_second = line.find(SECOND_DIGITS)
            if line_first != -1 and line_second != -1 and line_first > line_second:
                fail(errors, f"{rel}:{line_no} lists {SECOND_DIGITS} before {PRIMARY_DIGITS}")
            if line_second != -1 and PAIR not in line:
                fail(errors, f"{rel}:{line_no} shows {SECOND_DISPLAY} without the original ordered pair")

        if PAIR not in text:
            fail(errors, f"{rel} footer is missing the ordered phone pair")
        if rel.as_posix() == "contact.html" and text.count(PAIR) < 2:
            fail(errors, "contact.html lede is missing the ordered phone pair")
        if rel.as_posix() in {"privacy.html", "terms.html"}:
            solo = f"<p>Phone: <a href=\"{PRIMARY_TEL}\">{PRIMARY_DISPLAY}</a></p>"
            if text.count(solo) != 1:
                fail(errors, f"{rel} contact block should keep only {PRIMARY_DISPLAY}")


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
