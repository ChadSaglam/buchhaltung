"""UBS Kontoauszug PDF parser — extracts transactions using pdfplumber."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import BinaryIO

import pdfplumber


def _parse_swiss_number(text: str) -> float | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    # Both apostrophes: statements in the wild use the typographic U+2019, and
    # anything this product printed itself uses the plain U+0027 (fpdf2's core
    # fonts are latin-1). Reading back our own PDF used to fail on that alone.
    # U+00A0 and U+202F are the no-break spaces Swiss statements group with.
    for mark in ("\u2019", "'", "\u00b4", ",", " ", "\u00a0", "\u202f"):
        text = text.replace(mark, "")
    try:
        return float(text)
    except ValueError:
        return None


def _reconstruct_number(words: list) -> float | None:
    if not words:
        return None
    sorted_words = sorted(words, key=lambda w: w["x0"])
    combined = "".join(w["text"] for w in sorted_words)
    return _parse_swiss_number(combined)


def _reconstruct_text(words: list) -> str:
    if not words:
        return ""
    sorted_words = sorted(words, key=lambda w: w["x0"])
    return " ".join(w["text"] for w in sorted_words)


#: A statement date, and nothing else on the line (B-56).
#:
#: This used to be ``re.compile(r"\d{2}\.\d{2}\.\d{2}").match(...)`` — unanchored
#: at the end, so ``31.12.2024`` matched on its first eight characters and the
#: two-digit-year rule below then read ``2024`` as the year: ``1900 + 2024``,
#: and the booking landed in **3924**. UBS prints ``dd.mm.yy``, other banks print
#: ``dd.mm.yyyy``, and nothing said which one this parser was for.
DATE_PATTERN = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2}|\d{4})$")


def parse_statement_date(text: str) -> str | None:
    """``dd.mm.yy`` or ``dd.mm.yyyy`` → ``dd.mm.yyyy``. None when it is not a date."""
    match = DATE_PATTERN.match((text or "").strip())
    if match is None:
        return None
    tag, monat, jahr = match.groups()
    if len(jahr) == 4:
        volles_jahr = int(jahr)
    else:
        # A statement is a recent document; a two-digit year below 50 is this
        # century. The cut-off only matters for archives older than the product.
        zweistellig = int(jahr)
        volles_jahr = 2000 + zweistellig if zweistellig < 50 else 1900 + zweistellig
    if not (1 <= int(monat) <= 12 and 1 <= int(tag) <= 31):
        return None
    return f"{tag}.{monat}.{volles_jahr}"


def extract_transactions_from_pdf(pdf_file: BinaryIO) -> list[dict]:
    """Extract transactions from a UBS Kontoauszug PDF.

    Returns list of dicts with keys:
    Datum, Beschreibung, Belastung, Gutschrift, Betrag CHF
    """
    transactions: list[dict] = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=2)
            if not words:
                continue

            # Find header row
            header_y = None
            for w in words:
                if w["text"] == "Datum":
                    header_y = w["top"]
                    break
            if header_y is None:
                continue

            # Collect header positions
            headers: dict = {}
            for w in words:
                if abs(w["top"] - header_y) < 3:
                    headers[w["text"]] = w

            belast_right = headers.get("Belastungen", {}).get("x1", 329)
            gutschr_right = headers.get("Gutschriften", {}).get("x1", 414)
            info_left = headers.get("Informationen", {}).get("x0", 84)
            belast_left = belast_right - 60
            gutschr_left = belast_right + 10

            # Group words by line
            line_groups: dict[float, list] = defaultdict(list)
            for w in words:
                if w["top"] < header_y + 3:
                    continue
                y_key = round(w["top"])
                line_groups[y_key].append(w)

            # Merge close lines
            sorted_ys = sorted(line_groups.keys())
            merged: dict[float, list] = {}
            for y in sorted_ys:
                found = False
                for key in merged:
                    if abs(y - key) < 3:
                        merged[key].extend(line_groups[y])
                        found = True
                        break
                if not found:
                    merged[y] = list(line_groups[y])

            pending_details: list[str] = []
            page_height = page.height

            for y in sorted(merged.keys()):
                line_words = merged[y]
                if y > page_height * 0.88:
                    continue

                datum_words = [w for w in line_words if w["x1"] < info_left]
                info_words = [w for w in line_words if info_left - 2 <= w["x0"] < belast_left]
                belast_words = [w for w in line_words if belast_left <= w["x0"] and w["x1"] <= belast_right + 5]
                gutschr_words = [w for w in line_words if gutschr_left <= w["x0"] and w["x1"] <= gutschr_right + 5]

                datum_text = _reconstruct_text(datum_words)

                gelesen = parse_statement_date(datum_text)
                if gelesen is not None:
                    # Flush pending details to previous transaction
                    if pending_details and transactions:
                        transactions[-1]["Beschreibung"] += " " + " ".join(pending_details)
                    pending_details = []

                    date_str = gelesen

                    info_text = _reconstruct_text(info_words)
                    info_lower = info_text.lower()
                    skip_kw = [
                        "anfangssaldo",
                        "schlusssaldo",
                        "umsatztotal",
                        "formular ohne",
                    ]
                    if any(kw in info_lower for kw in skip_kw):
                        continue

                    belastung = _reconstruct_number(belast_words)
                    gutschrift = _reconstruct_number(gutschr_words)
                    if belastung is None and gutschrift is None:
                        continue

                    amount = gutschrift if gutschrift else belastung
                    transactions.append(
                        {
                            "Datum": date_str,
                            "Beschreibung": info_text.strip(),
                            "Belastung": belastung,
                            "Gutschrift": gutschrift,
                            "Betrag CHF": amount if amount else 0,
                        }
                    )
                else:
                    info_text = _reconstruct_text(info_words)
                    cleaned = info_text.strip()
                    skip_words = [
                        "formular ohne",
                        "seite",
                        "gnzkoa",
                        "ubs switzerland",
                        "freundliche gr",
                        "bitten sie",
                        "benachrichtigen",
                        "umsatztotal",
                        "schlusssaldo",
                        "unstimmigkeiten",
                        "diesen auszug",
                        "innert 30 tagen zu",
                        "ubs kontokorrent",
                        "rds isolierungen",
                        "effretikon",
                        "erstellt am",
                        "kontoauszug 0",
                    ]
                    if cleaned and not any(s in cleaned.lower() for s in skip_words):
                        pending_details.append(cleaned)

            if pending_details and transactions:
                transactions[-1]["Beschreibung"] += " " + " ".join(pending_details)

    # Clean boilerplate
    boilerplate = [
        r"Sie,.+benachrichtigen\.",
        r"Gr.{1,5}e\.",
        r"hne Unterschrift\.",
        # "Freundliche Grüsse UBS Switzerland AG" split across lines leaves "Grüße AG" on the last row.
        r"\b(?:Freundliche\s+)?Gr(?:ü|ue|u)(?:ss|ß)e(?:\s+UBS)?(?:\s+Switzerland)?(?:\s+AG)?\s*$",
    ]
    for tx in transactions:
        desc = tx["Beschreibung"]
        for pat in boilerplate:
            desc = re.sub(pat, "", desc)
        tx["Beschreibung"] = desc.strip()

    return transactions
