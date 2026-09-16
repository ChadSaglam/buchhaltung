"""What has to end up in the audit log, and why (B-22).

The list is here rather than scattered across the routers because it is a
*contract*, not an implementation detail: `50-Protokoll.csv` in the Treuhänder
hand-off (B-17) is this table, and a gap here is a gap in the hand-off. Before
2026-09-16 the log held six actions, four of them added the same week — so the
pack's audit extract would have been very nearly empty, which is worse than not
shipping one.

The test in `tests/test_audit_completeness.py` drives every operation below
through the API and asserts a row appears, so an endpoint that stops recording
fails the suite rather than going quiet.

The bar for being on this list: **would a Treuhänder, an auditor or the owner
six months from now ask "who did this, and when?"** That is money moving,
something leaving the building, or something that cannot be undone. Reads are
not on it, and neither is anything the system does to itself — a scheduled
import that nobody chose is noise in a log meant to answer a question about a
person.
"""

from __future__ import annotations

#: action → what it records. Keep the prefix as the surface it belongs to.
AUDIT_ACTIONS: dict[str, str] = {
    # Accounting records themselves.
    "booking.create": "Buchungen erfasst — the accounting record, from any source",
    "kontenplan.update": "Kontenplan geändert — every later booking is classified against it",
    "import.banana": "Buchungen importiert — a bulk write nobody sees line by line",
    # Money leaving or being claimed.
    "rechnung.create": "Rechnung geschrieben — a claim against a customer",
    "rechnung.versand": "Rechnung verschickt — it left the building",
    "mahnung.record": "Mahnung erfasst — a dunning step with legal weight",
    "lohn.abrechnung": "Lohn abgerechnet und verbucht — irreversible by design",
    "lohn.freigabe": "Lohn-Einrichtung freigegeben — lifts the payslip watermark",
    "lohn.mitarbeiter.neu": "Mitarbeiter angelegt",
    # Decisions about what a movement means.
    "abgleich.confirm": "Bankzeile einem Beleg zugeordnet",
    "abgleich.reject": "Zuordnungsvorschlag abgelehnt",
    "abgleich.manual": "Bankzeile von Hand zugeordnet",
    "abgleich.ignore": "Bankzeile als irrelevant markiert",
    "review.approve": "Unsichere Buchung bestätigt",
    "review.reject": "Unsichere Buchung korrigiert",
    "document.status": "Belegstatus geändert — offen ↔ bezahlt is a payment assertion",
    # Handing over.
    "export.batch": "Export erstellt — the bookings are stamped and leave for the Treuhand",
}

#: Deliberately *not* audited, so the next person does not add them by reflex.
NICHT_PROTOKOLLIERT: dict[str, str] = {
    "every read": "an audit log of who looked at what answers no question anyone asks here",
    "document upload": "the document row and its created_at already are the record",
    "scheduled imports": "nobody chose them; a log meant to name a person should not be full of the system",
    "classification": "the model proposing an account is not a decision — accepting it is, and that is review.*",
}
