"""Import Banana Buchhaltung XLS/CSV as training data + memory."""
from __future__ import annotations

import io
import re
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.training_data import TrainingRow
from app.models.memory import Memory
from app.services.classifier import TenantClassifier, make_memory_key

router = APIRouter(prefix="/api/import", tags=["import"])


def parse_banana_xls(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse Banana Buchhaltung export (XLS/XLSX/CSV/XML) into training rows."""
    import pandas as pd

    # Detect format by file signature
    header = file_bytes[:20]

    if header.startswith(b"<?xml") or header.startswith(b"\xef\xbb\xbf<?xml"):
        import xml.etree.ElementTree as ET
        raw = file_bytes.decode("utf-8", errors="replace")
        if raw.startswith("\ufeff"):
            raw = raw[1:]

        # Parse with namespace awareness instead of stripping
        namespaces = {
            'ss': 'urn:schemas-microsoft-com:spreadsheet',
            'o': 'urn:schemas-microsoft-com:office:office',
            'x': 'urn:schemas-microsoft-com:office:excel',
        }
        root = ET.fromstring(raw)

        # Find the Worksheet/Table
        ns = 'urn:schemas-microsoft-com:spreadsheet'
        table = root.find(f'.//{{{ns}}}Table')
        if table is None:
            # Try without namespace
            raw_clean = re.sub(r'<(/?)(\w+):', r'<\1', raw)
            raw_clean = re.sub(r'\s+xmlns(:[^=]*)?\s*=\s*"[^"]*"', '', raw_clean)
            raw_clean = re.sub(r'\s+\w+:(\w+)=', r' \1=', raw_clean)
            root = ET.fromstring(raw_clean)
            table = root.find('.//Table')
            ns = ''

        if table is None:
            raise HTTPException(400, "Keine Tabelle in der XML-Datei gefunden.")

        all_rows = []
        tag_row = f'{{{ns}}}Row' if ns else 'Row'
        tag_cell = f'{{{ns}}}Cell' if ns else 'Cell'
        tag_data = f'{{{ns}}}Data' if ns else 'Data'
        attr_index = f'{{{ns}}}Index' if ns else 'Index'

        for row_el in table.findall(tag_row):
            cells = []
            col_idx = 0
            for cell in row_el.findall(tag_cell):
                # Handle ss:Index (1-based column skip)
                idx_attr = cell.get(attr_index) or cell.get('Index')
                if idx_attr:
                    target = int(idx_attr) - 1
                    while col_idx < target:
                        cells.append("")
                        col_idx += 1

                data_el = cell.find(tag_data)
                cells.append(data_el.text if data_el is not None and data_el.text else "")
                col_idx += 1
            all_rows.append(cells)

        if len(all_rows) < 2:
            raise HTTPException(400, "Zu wenige Zeilen in der XML-Datei.")

        headers = all_rows[0]
        data_rows = all_rows[1:]

        max_cols = len(headers)
        data_rows = [r[:max_cols] + [""] * max(0, max_cols - len(r)) for r in data_rows]
        df = pd.DataFrame(data_rows, columns=headers)

        import logging
        logging.warning(f"Banana import: {len(df)} rows, columns = {list(df.columns)[:10]}")

    elif header.startswith(b"PK\x03\x04"):
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    elif header.startswith(b"\xd0\xcf\x11\xe0"):
        df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
    elif filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), sep=None, engine="python")
    else:
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        except Exception:
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
            except Exception as e:
                raise HTTPException(400, f"Unbekanntes Dateiformat: {str(e)}")

    # Normalize column names
    col_map = {}
    for col in df.columns:
        cl = str(col).strip().lower()
        if cl in ("description", "beschreibung"):
            col_map[col] = "Beschreibung"
        elif cl in ("accountdebit", "ktsoll", "kontosoll", "account debit"):
            col_map[col] = "KtSoll"
        elif cl in ("accountdebitdes", "ktsoll beschr.", "ktsoll beschr"):
            col_map[col] = "KtSollBeschr"
        elif cl in ("accountcredit", "kthaben", "kontokredit", "account credit"):
            col_map[col] = "KtHaben"
        elif cl in ("vatcode", "mwstust-code", "mwst_code", "mwstcode"):
            col_map[col] = "MwStCode"
        elif cl in ("vatrate", "mwstust", "mwst_pct", "mwstustproz"):
            col_map[col] = "MwStPct"
        elif cl in ("amount", "betrag"):
            col_map[col] = "Betrag"

    df = df.rename(columns=col_map)

    # Log actual columns for debugging
    import logging
    logging.warning(f"Banana import: columns after rename = {list(df.columns)}")
    logging.warning(f"Banana import: first 3 rows = {df.head(3).to_dict()}")

    required = {"Beschreibung", "KtSoll"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(
            400,
            f"Benötigte Spalten fehlen: {required - set(df.columns)}. "
            f"Gefundene Spalten: {list(df.columns)[:30]}"
        )

    rows = []
    for _, row in df.iterrows():
        beschreibung = str(row.get("Beschreibung", "")).strip()
        kt_soll = str(row.get("KtSoll", "")).strip()
        if not beschreibung or not kt_soll or kt_soll == "nan":
            continue
        # Skip rows where kt_soll is not a valid account number
        if not re.match(r'^\d{4}$', kt_soll):
            continue
        kt_haben = str(row.get("KtHaben", "1020")).strip() if pd.notna(row.get("KtHaben")) else "1020"
        if not re.match(r'^\d{4}$', kt_haben):
            kt_haben = "1020"
        mwst_code = str(row.get("MwStCode", "")).strip() if pd.notna(row.get("MwStCode")) else ""
        mwst_pct = str(row.get("MwStPct", "")).strip() if pd.notna(row.get("MwStPct")) else ""
        rows.append({
            "beschreibung": beschreibung[:500],
            "kt_soll": kt_soll[:20],
            "kt_haben": kt_haben[:20],
            "mwst_code": mwst_code[:10],
            "mwst_pct": mwst_pct[:10],
        })
    return rows




@router.post("/banana")
async def import_banana_file(
    file: UploadFile = File(...),
    replace: bool = False,
    also_memory: bool = True,
    auto_train: bool = True,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import a Banana Buchhaltung XLS export as training data.
    
    - replace: if True, delete existing training data first
    - also_memory: if True, also populate memory table for exact matches
    - auto_train: if True, retrain model after import
    """
    content = await file.read()
    rows = parse_banana_xls(content, file.filename or "data.xls")

    if not rows:
        raise HTTPException(400, "Keine gültigen Buchungen gefunden.")

    tid = user.tenant_id

    if replace:
        await db.execute(delete(TrainingRow).where(TrainingRow.tenant_id == tid))

    # Bulk insert training data
    seen_keys: set[str] = set()
    training_objects = []
    memory_objects = []

    for r in rows:
        training_objects.append(TrainingRow(
            tenant_id=tid,
            beschreibung=r["beschreibung"],
            kt_soll=r["kt_soll"],
            kt_haben=r["kt_haben"],
            mwst_code=r["mwst_code"],
            mwst_pct=r["mwst_pct"],
        ))

        if also_memory:
            key = make_memory_key(r["beschreibung"])
            if key and key not in seen_keys:
                seen_keys.add(key)
                # Upsert memory
                existing = await db.execute(
                    select(Memory).where(Memory.tenant_id == tid, Memory.lookup_key == key)
                )
                mem = existing.scalar_one_or_none()
                if mem:
                    mem.kt_soll = r["kt_soll"]
                    mem.kt_haben = r["kt_haben"]
                    mem.mwst_code = r["mwst_code"]
                    mem.mwst_pct = r["mwst_pct"]
                else:
                    memory_objects.append(Memory(
                        tenant_id=tid, lookup_key=key,
                        kt_soll=r["kt_soll"], kt_haben=r["kt_haben"],
                        mwst_code=r["mwst_code"], mwst_pct=r["mwst_pct"],
                    ))

    db.add_all(training_objects)
    db.add_all(memory_objects)
    await db.flush()

    result = {"imported": len(training_objects), "memory_entries": len(memory_objects) + len(seen_keys)}

    if auto_train:
        clf = TenantClassifier(tid, db)
        train_result = await clf.train_from_db()
        result["training"] = train_result

    await db.commit()
    return result


@router.post("/banana-text")
async def import_banana_text(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import from raw paste text (the paste-6.txt tab-separated format)."""
    import pandas as pd

    raw_text = body.get("text", "")
    if not raw_text.strip():
        raise HTTPException(400, "Kein Text angegeben.")

    lines = raw_text.strip().split("\n")
    # Parse tab-separated Banana format
    rows = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 10:
            continue
        # Find Description and AccountDebit columns by position
        # Banana format: Section, Date, ..., Description, Notes, AccountDebit, ..., AccountCredit, ..., Amount, ...
        beschreibung = ""
        kt_soll = ""
        kt_haben = ""
        betrag = ""
        mwst_code = ""
        mwst_pct = ""

        for i, p in enumerate(parts):
            p_clean = p.strip()
            if re.match(r"^\d{4}$", p_clean) and not kt_soll:
                # Could be an account number
                if i > 5:  # Skip date-like positions
                    kt_soll = p_clean
                    # Next 4-digit is kt_haben
                    for j in range(i + 2, min(i + 4, len(parts))):
                        if re.match(r"^\d{4}$", parts[j].strip()):
                            kt_haben = parts[j].strip()
                            break

        # This is complex — better to use the structured parse
        # Recommend uploading XLS instead

    raise HTTPException(501, "Bitte XLS-Datei hochladen statt Text-Paste.")
