"""Parse raw Banana Buchhaltung tab-separated export."""
from __future__ import annotations
import re


def parse_banana_text(raw: str) -> list[dict]:
    """Parse the paste-6.txt style Banana export into structured rows."""
    rows = []
    lines = raw.strip().split("\n")
    
    # Skip header lines (contain 'Section', 'Date', etc.)
    data_lines = [l for l in lines if not l.startswith("Section") and not l.startswith("Sektion")]
    
    for line in data_lines:
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 15:
            continue

        # Banana column positions (from the actual export):
        # The Description is typically around index 12-13
        # AccountDebit ~14-15, AccountCredit ~16-17, Amount ~18
        beschreibung = ""
        kt_soll = ""
        kt_haben = ""
        mwst_code = ""
        mwst_pct = ""
        betrag = ""

        # Find 4-digit account codes and description
        account_indices = []
        for i, p in enumerate(parts):
            if re.match(r"^\d{4}$", p):
                account_indices.append(i)

        if len(account_indices) >= 2:
            kt_soll_idx = account_indices[0]
            kt_haben_idx = account_indices[1]
            kt_soll = parts[kt_soll_idx]
            kt_haben = parts[kt_haben_idx]
            
            # Description is typically 2 positions before first account
            desc_idx = kt_soll_idx - 2
            if 0 <= desc_idx < len(parts) and len(parts[desc_idx]) > 2:
                beschreibung = parts[desc_idx]

        if beschreibung and kt_soll:
            rows.append({
                "beschreibung": beschreibung,
                "kt_soll": kt_soll,
                "kt_haben": kt_haben or "1020",
                "mwst_code": mwst_code,
                "mwst_pct": mwst_pct,
            })

    return rows
