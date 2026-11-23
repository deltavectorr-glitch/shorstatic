#!/usr/bin/env python3
"""Checks for the public donate path.

Simulates the two Vercel orders that matter here:
- redirects before the cleanUrls .html strip
- the .html strip before redirects (what production does for missing files)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERCEL = ROOT / "vercel.json"

REQUIRED_FACTS = [
    "SHRIHARIOMRAM FOUNDATION",
    "122488700000014",
    "YESB0001224",
    "YES Bank",
    "yespay.smessi10351937@yesbankltd",
    "NEFT/IMPS/RTGS",
    "ABOCS3386D",
    "DL/2024/0452487",
    "ABOCS3386DE20241",
    "ABOCS3386DF20241",
    "Form 10AC",
    "28-10-2024",
    "AY 2025-26 to AY 2027-28",
    "12-Sub-clause (A) of clause (iv) of first proviso to sub-section (5) of section 80G",
    "support@shorfoundation.in",
    "UTR/UPI reference",
    "provisional registration",
    "provisional approval",
    "We can currently accept donations only from Indian citizens and Indian-source funds.",
    "02-Item (A) of sub-clause (vi) of clause (ac) of sub-section (1) of section 12A",
]

PROVISIONAL_SENTENCE = (
    "SHRIHARIOMRAM FOUNDATION holds provisional registration under section 12A "
    "(URN ABOCS3386DE20241) and provisional approval under section 80G "
    "(URN ABOCS3386DF20241), vide Form 10AC dated 28-10-2024, valid AY 2025-26 to AY 2027-28. "
    "Donations may be eligible for deduction under section 80G, subject to applicable law."
)

RECEIPT_LINE = (
    "After giving, email your name, PAN, address, amount, date and UTR/UPI reference to "
    '<a href="mailto:support@shorfoundation.in">support@shorfoundation.in</a>. '
    "We will issue Form 10BE within 7 days of receiving "
    "complete details. Donations are reported in Form 10BD / Form 113 as required. Your PAN and "
    "address are used only to issue the receipt and to file the statutory donation return; they "
    "are not used for marketing."
)

LEDE = "Give by bank transfer (NEFT/IMPS/RTGS) or UPI. This page is for individual donors and CSR desks."

GIVE_NAV = ["Work", "Events", "About", "Contact", "Donate"]

FORBIDDEN = [
    "full platform",
    "razorpay",
    "payment gateway",
    "upi://",
]

UPI_QR_SRC = "/images/upi-qr-shrihariomram.png"
UPI_QR_FILE = ROOT / "images" / "upi-qr-shrihariomram.png"

NAV_LABELS = ["Work", "Solutions", "Events", "About", "Contact", "Donate"]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.desktop: list[tuple[str, str]] = []
        self.mobile: list[tuple[str, str]] = []
        self.cta: list[tuple[str, str]] = []
        self.footer_give: list[tuple[str, str]] = []
        self._capture: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        self.stack.append((tag, attr))
        if tag != "a":
            return
        classes = attr.get("class", "")
        href = attr.get("href", "")
        if "mkt-nav-cta" in classes:
            self._capture = "cta"
            self._buf = []
            self.cta.append((href, ""))
            return
        parent_classes = ""
        for parent, parent_attr in reversed(self.stack[:-1]):
            if parent == "div":
                parent_classes = parent_attr.get("class", "")
                break
        if "nav-panel" in parent_classes:
            self._capture = "mobile"
            self._buf = []
            self.mobile.append((href, ""))
        elif "lg:flex" in parent_classes and "mkt-nav-cta" not in classes:
            self._capture = "desktop"
            self._buf = []
            self.desktop.append((href, ""))
        elif href.endswith("give.html") and "Give / CSR" in "":
            pass

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture:
            text = "".join(self._buf).strip()
            bucket = {
                "cta": self.cta,
                "mobile": self.mobile,
                "desktop": self.desktop,
            }[self._capture]
            href, _ = bucket[-1]
            bucket[-1] = (href, text)
            self._capture = None
            self._buf = []
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)
        if "Give / CSR" in data:
            for parent, attr in reversed(self.stack):
                if parent == "a":
                    self.footer_give.append((attr.get("href", ""), "Give / CSR"))
                    break


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_redirects() -> list[dict]:
    config = json.loads(VERCEL.read_text())
    if config.get("cleanUrls") is not True:
        raise AssertionError("cleanUrls must stay true")
    return list(config.get("redirects") or [])


def apply_redirect(path: str, redirects: list[dict]) -> str | None:
    for rule in redirects:
        if rule.get("source") == path:
            return rule["destination"]
    return None


def follow(path: str, redirects: list[dict], html_first: bool) -> tuple[int, str]:
    seen: list[str] = []
    for _ in range(6):
        if path in seen:
            return 508, "redirect loop " + " -> ".join(seen + [path])
        seen.append(path)
        if html_first and path.endswith(".html"):
            path = path[: -len(".html")] or "/"
            continue
        dest = apply_redirect(path, redirects)
        if dest:
            path = dest
            continue
        if not html_first and path.endswith(".html"):
            path = path[: -len(".html")] or "/"
            continue
        rel = "index.html" if path in ("", "/") else path.lstrip("/") + ".html"
        file = ROOT / rel
        if file.is_file():
            return 200, file.read_text()
        return 404, "missing " + rel
    return 508, "too many redirects"


def check_page(errors: list[str]) -> None:
    give = (ROOT / "give.html").read_text()
    if "How to donate" not in give:
        fail(errors, "give.html is missing the How to donate section")
    if PROVISIONAL_SENTENCE not in give:
        fail(errors, "give.html is missing the approved provisional tax sentence")
    if not re.search(r">\s*Provisional\s*<", give):
        fail(errors, "tax note is not clearly labelled Provisional")
    for fact in REQUIRED_FACTS:
        if fact not in give:
            fail(errors, f"give.html is missing approved detail: {fact}")
    lowered = give.lower()
    for banned in FORBIDDEN:
        if banned in lowered:
            fail(errors, f"give.html still contains {banned!r}")
    for cta in ("contact.html?type=DONOR", "contact.html?type=PARTNER"):
        if cta not in give:
            fail(errors, f"donor/CSR CTA missing: {cta}")
    if RECEIPT_LINE not in give:
        fail(errors, "give.html receipt line does not match the approved text")
    if LEDE not in give:
        fail(errors, "give.html lede does not match the approved text")
    if "public brief" in give or "Children Supported Annually" in give or "400+" in give:
        fail(errors, "give.html still has the old lede or the impact rail")
    if "solutions.html" in give or ">Solutions<" in give:
        fail(errors, "give.html still links to Solutions")
    if "We can currently accept gifts from Indian donors." in give:
        fail(errors, "give.html still has the old Indian-donor line")
    hero = give.split("<section", 1)[0]
    for banned in ("counter-uav", "Counter-UAV", "C-UAV"):
        if banned in hero:
            fail(errors, f"donate nav/hero promotes {banned}")
    privacy = (ROOT / "privacy.html").read_text()
    if "info@shorfoundation.com" in privacy:
        fail(errors, "privacy.html still lists info@shorfoundation.com")
    if "contacting us at support@shorfoundation.in." not in privacy:
        fail(errors, "privacy consent line does not use support@shorfoundation.in.")
    if "support@shorfoundation.in ." in privacy:
        fail(errors, "privacy consent line has a space before the period")
    if "our organisation" not in privacy:
        fail(errors, "privacy.html does not say our organisation")
    if "our organization" in privacy:
        fail(errors, "privacy.html still says our organization")


def check_sitewide(errors: list[str]) -> None:
    pages = sorted(ROOT.rglob("*.html"))
    for page in pages:
        text = page.read_text()
        rel = page.relative_to(ROOT)
        if ">Organization</p>" in text:
            fail(errors, f"{rel} footer still says Organization")
        if ">Organisation</p>" not in text:
            fail(errors, f"{rel} footer is missing Organisation")
        if "+91-8099010839" in text:
            fail(errors, f"{rel} still has the mismatched phone number")
        for number, href in (
            ("+91 80901 08939", 'href="tel:+918090108939"'),
            ("+91 95991 54905", 'href="tel:+919599154905"'),
        ):
            if number in text and href not in text:
                fail(errors, f"{rel} shows {number} without {href}")
            if text.count(number) != text.count(href):
                fail(errors, f"{rel} phone link count for {number} does not match")
        allowed_tels = {"tel:+918090108939", "tel:+919599154905"}
        for href in re.findall(r'href="(tel:[^"]*)"', text):
            if href not in allowed_tels:
                fail(errors, f"{rel} tel link is {href}")
        first = text.find("8090108939")
        second = text.find("9599154905")
        if first != -1 and second != -1 and first > second:
            fail(errors, f"{rel} lists 9599154905 before 8090108939")


def check_nav(errors: list[str]) -> None:
    pages = sorted(ROOT.rglob("*.html"))
    if not pages:
        fail(errors, "no html pages found")
    for page in pages:
        parser = LinkParser()
        parser.feed(page.read_text())
        rel = page.relative_to(ROOT)
        expected = GIVE_NAV if rel.as_posix() == "give.html" else NAV_LABELS
        if [text for _, text in parser.desktop] != expected:
            fail(errors, f"{rel} desktop nav is {[text for _, text in parser.desktop]}")
        if [text for _, text in parser.mobile] != expected:
            fail(errors, f"{rel} mobile nav is {[text for _, text in parser.mobile]}")
        if parser.cta != [("/give", "Donate")]:
            fail(errors, f"{rel} header CTA is {parser.cta}")
        for href, text in parser.desktop + parser.mobile:
            if text == "Donate" and href != "/give":
                fail(errors, f"{rel} Donate href is {href}, expected /give")
            if href.startswith("/"):
                target = ROOT / f"{href.lstrip('/')}.html"
            else:
                target = (page.parent / href).resolve()
            if not target.is_file():
                fail(errors, f"{rel} nav link {href} does not resolve")
        if parser.footer_give != [("/give", "Give / CSR")]:
            fail(errors, f"{rel} footer Give link is {parser.footer_give}")
        if rel.as_posix() == "give.html":
            donate = [href for href, text in parser.desktop if text == "Donate"]
            row = page.read_text()
            if 'href="/give" class="text-[#f3f1ec]' not in row:
                fail(errors, "give.html does not mark Donate as the current desktop item")
            if donate != ["/give"]:
                fail(errors, "give.html Donate item missing")


def upi_param(payload: str, name: str) -> str:
    query = payload.split("?", 1)[1] if "?" in payload else ""
    for part in query.split("&"):
        key, sep, value = part.partition("=")
        if sep and key == name:
            return value
    return ""


def qr_payload(path: Path) -> str | None:
    """Decoded QR text. None means no decoder is installed."""
    try:
        from pyzbar.pyzbar import decode as zbar_decode
        from PIL import Image
    except ImportError:
        zbar_decode = None
    else:
        try:
            found = zbar_decode(Image.open(path))
        except Exception:
            found = None
        else:
            if not found:
                return ""
            return found[0].data.decode("utf-8")
    zbarimg = shutil.which("zbarimg")
    if not zbarimg:
        return None
    proc = subprocess.run(
        [zbarimg, "--raw", "-q", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = proc.stdout.strip()
    if proc.returncode != 0 or not text:
        return ""
    return text.splitlines()[0]


def check_qr(errors: list[str]) -> None:
    give = (ROOT / "give.html").read_text()
    if UPI_QR_SRC not in give:
        fail(errors, f"give.html does not reference {UPI_QR_SRC}")
    if not UPI_QR_FILE.is_file():
        fail(errors, f"UPI QR file is missing: {UPI_QR_FILE.relative_to(ROOT)}")
        return
    payload = qr_payload(UPI_QR_FILE)
    if payload is None:
        return
    pa = upi_param(payload, "pa")
    pn = upi_param(payload, "pn")
    if pa != "yespay.smessi10351937@yesbankltd":
        fail(errors, f"UPI QR pa is {pa!r}")
    if pn != "SHRIHARIOMRAM FOUNDATION":
        fail(errors, f"UPI QR pn is {pn!r}")


def check_routes(errors: list[str]) -> None:
    redirects = load_redirects()
    sources = {rule.get("source"): rule.get("destination") for rule in redirects}
    if sources.get("/donate") != "/give":
        fail(errors, f"/donate redirect is {sources.get('/donate')!r}")
    if sources.get("/donate.html") != "/give":
        fail(errors, f"/donate.html redirect is {sources.get('/donate.html')!r}")
    for html_first in (False, True):
        for path in ("/donate", "/donate.html", "/give", "/give.html"):
            status, body = follow(path, redirects, html_first)
            order = "html-first" if html_first else "redirect-first"
            if status != 200:
                fail(errors, f"{order} {path} -> {status} {body[:120]}")
                continue
            if "122488700000014" not in body or "How to donate" not in body:
                fail(errors, f"{order} {path} did not land on the donate page")


def main() -> None:
    errors: list[str] = []
    check_page(errors)
    check_qr(errors)
    check_sitewide(errors)
    check_nav(errors)
    check_routes(errors)
    if errors:
        print(f"{len(errors)} check(s) failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("donate checks passed")


if __name__ == "__main__":
    main()
