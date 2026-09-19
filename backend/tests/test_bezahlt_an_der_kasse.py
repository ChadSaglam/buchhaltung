"""B-89: a till receipt paid by card is not an open payable.

The rule has to be conservative in one direction only. A missed receipt costs
the owner one click on the checkbox; a false positive hides a real debt from
"Was schulden wir", which is the failure this whole item is about.
"""

from __future__ import annotations

from app.services.bezahlt_an_der_kasse import bezahlt_an_der_kasse

# The receipt from the first real run, 2026-09-17 (Landi Thula TopShop, Matzingen).
LANDI = """
LANDI THULA TopShop Matzingen
BLEIFREI 95          58.48
Total                58.48
Erhalten: MASTERCARD 58.48
DEBIT MASTERCARD contactless
"""


def test_the_receipt_from_the_first_run_is_recognised():
    assert bezahlt_an_der_kasse(LANDI, hat_faelligkeit=False) is True


def test_a_due_date_vetoes_every_marker():
    """A supplier invoice whose footer accepts cards is still a payable."""
    text = "Rechnung Nr. 4711\nZahlbar bis 30.10.2026\nWir akzeptieren Visa, Mastercard, contactless"
    assert bezahlt_an_der_kasse(text, hat_faelligkeit=True) is False


def test_the_veto_holds_even_for_the_landi_text():
    assert bezahlt_an_der_kasse(LANDI, hat_faelligkeit=True) is False


def test_cash_and_twint_count_too():
    for text in ("Erhalten: BAR 12.50", "Erhalten: TWINT 40.00", "Barzahlung", "Total-EFT 58.48"):
        assert bezahlt_an_der_kasse(text, hat_faelligkeit=False) is True, text


def test_a_bare_card_brand_is_not_enough():
    """'Wir akzeptieren Mastercard' in a footer says nothing about this invoice."""
    for text in ("Wir akzeptieren Mastercard und Visa", "Zahlung per Karte möglich", "Kreditkarte"):
        assert bezahlt_an_der_kasse(text, hat_faelligkeit=False) is False, text


def test_empty_text_is_not_a_claim():
    assert bezahlt_an_der_kasse("", hat_faelligkeit=False) is False
    assert bezahlt_an_der_kasse(None, hat_faelligkeit=False) is False  # type: ignore[arg-type]
