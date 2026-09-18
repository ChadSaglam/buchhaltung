"""B-89: did this receipt already pay itself at the till?

A Landi/Agrola fuel receipt read on the first real run (2026-09-17) says
``Erhalten: MASTERCARD 58.48`` and ``DEBIT MASTERCARD contactless``. The money
left the account on the spot. It is still a document the Abgleich has to match
against a bank line, so its ``status`` stays ``offen`` — but it is not a
payable, and Offene Posten must not present it as one.

This module answers the question from text alone, and it answers it
*conservatively*: the checkbox on the Beleg is the authority, this is only what
the box is pre-ticked with. A false positive would hide a real debt, so two
things must hold together — a payment marker in the text **and** no due date.
A supplier invoice that happens to print "Zahlung per Karte möglich" carries a
Fälligkeitsdatum and is therefore never caught by this.

Deliberately not in the classifier: this is not a Kontierung question. The
account was already right on the first run; what was wrong was the claim that
somebody was owed money.
"""

from __future__ import annotations

import re

# Markers that the amount was *received* at the point of sale. Kept narrow on
# purpose: "Karte", "Visa" or "Mastercard" on their own also appear in the
# footer of invoices that merely accept cards.
_MARKER = re.compile(
    r"""(
      erhalten\s*[:\s]\s*(mastercard|visa|maestro|postcard|twint|bar|cash)
    | \b(debit\s*mastercard|debit\s*visa|v\s*pay)\b
    | \bcontactless\b
    | \btotal[-\s]?eft\b
    | \bkontaktlos\b
    | \bbar\s*(bezahlt|gegeben)\b
    | \bbarzahlung\b
    | \bbereits\s+bezahlt\b
    | \bzahlung\s+erfolgt\b
    | \bpaid\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def bezahlt_an_der_kasse(text: str, *, hat_faelligkeit: bool) -> bool:
    """True when the text shows the money left at the till and nothing is due later.

    ``hat_faelligkeit`` is the veto: a document with a Fälligkeitsdatum is asking
    to be paid, whatever its footer says about accepted cards.
    """
    if hat_faelligkeit:
        return False
    return bool(_MARKER.search(text or ""))
