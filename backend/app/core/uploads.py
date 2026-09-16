"""Grenzen für alles, was hochgeladen wird (B-54).

Bis hierher las jede Route erst ``await file.read()`` und prüfte danach die
Länge. Das ist die falsche Reihenfolge: eine 2-GB-Datei liegt dann bereits im
Speicher des Prozesses, wenn er "zu gross" sagt. Ein Upload, der abgelehnt
wird, soll den Speicher gar nicht erst kosten.

Drei Schichten, weil keine allein reicht:

* ``MaxBodySizeMiddleware`` liest ``Content-Length``, bevor überhaupt geroutet
  wird. Ehrliche Clients werden hier abgewiesen, ohne ein einziges Byte Body.
* ``read_upload`` liest in Blöcken und bricht ab, sobald das Limit überschritten
  ist. Das fängt den unehrlichen Client — ``Transfer-Encoding: chunked`` hat gar
  keine ``Content-Length`` — und erlaubt pro Route ein eigenes, kleineres Limit.
* ``zip_member`` prüft die *ausgepackte* Grösse aus dem Zip-Verzeichnis, bevor
  ``zf.read`` läuft. 40 kB komprimiert können 4 GB ausgepackt sein.
"""

from __future__ import annotations

import logging
import zipfile

from fastapi import HTTPException, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

MB = 1024 * 1024

#: Nothing this product accepts is larger than this. The per-route caps below
#: are tighter; this is the wall in front of the router.
MAX_REQUEST_BYTES = 64 * MB

#: Per kind of upload. A bank statement is the big one (a year of PDF).
MAX_PDF_BYTES = 50 * MB
MAX_STATEMENT_BYTES = 50 * MB
MAX_RECEIPT_BYTES = 20 * MB
MAX_IMPORT_BYTES = 32 * MB
MAX_MODEL_BUNDLE_BYTES = 64 * MB
#: A single member of an uploaded zip, *unpacked*.
MAX_ZIP_MEMBER_BYTES = 64 * MB
#: Everything in an uploaded zip, unpacked, together.
MAX_ZIP_TOTAL_BYTES = 128 * MB

#: List and mapping bounds — a JSON body is small on the wire and expensive in rows.
MAX_KONTENPLAN_ENTRIES = 5_000
MAX_MEMORY_ENTRIES = 100_000
MAX_BULK_BOOKINGS = 5_000

_CHUNK = MB


def _too_big(label: str, max_bytes: int) -> HTTPException:
    return HTTPException(413, f"{label} zu gross (max {max_bytes // MB} MB).")


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """413 on an oversized ``Content-Length``, before the router sees the request.

    Only a declared length is checked here — a client that lies, or sends
    chunked, is caught by :func:`read_upload` further in. Both layers exist
    because each one alone has a hole.
    """

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            logger.info("[UPLOAD] refused %s bytes on %s (cap %s)", declared, request.url.path, self.max_bytes)
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "payload_too_large",
                        "message": f"Anfrage zu gross (max {self.max_bytes // MB} MB).",
                    }
                },
            )
        return await call_next(request)


async def read_upload(file: UploadFile, *, max_bytes: int, label: str = "Datei") -> bytes:
    """Read an upload, giving up as soon as it is too large.

    The chunk that crosses the limit is the last one read: the process never
    holds more than ``max_bytes`` plus one chunk of a file it is going to
    refuse anyway.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise _too_big(label, max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def zip_member(
    archive: zipfile.ZipFile,
    name: str,
    *,
    max_bytes: int = MAX_ZIP_MEMBER_BYTES,
    label: str = "Datei im Archiv",
) -> bytes:
    """Read one member, refusing on its *declared unpacked* size.

    ``ZipInfo.file_size`` comes from the archive's own directory, so it is the
    attacker's number — but a zip bomb has to declare its size to be unpacked
    at all, and a lie in the other direction only makes the file smaller.
    """
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise HTTPException(400, f"{name} fehlt im Archiv.") from exc
    if info.file_size > max_bytes:
        raise _too_big(f"{label} ({name})", max_bytes)
    return archive.read(name)


def check_zip_total(archive: zipfile.ZipFile, *, max_bytes: int = MAX_ZIP_TOTAL_BYTES) -> None:
    """Refuse an archive whose members add up to more than we will ever unpack."""
    total = sum(info.file_size for info in archive.infolist())
    if total > max_bytes:
        raise _too_big("Archiv (entpackt)", max_bytes)


def check_count(items, *, max_items: int, label: str) -> None:
    """Bound a list or mapping from a JSON body — cheap on the wire, expensive in rows."""
    if len(items) > max_items:
        raise HTTPException(413, f"Zu viele {label} (max {max_items:,}).".replace(",", "'"))
