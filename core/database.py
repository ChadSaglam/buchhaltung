"""
PostgreSQL database support for bookkeeping data.

Uses psycopg2 to connect via DATABASE_URL from .env.
Gracefully handles missing dependencies or configuration.
"""

from __future__ import annotations

import os
import pathlib
from datetime import datetime

import pandas as pd


def _load_database_url() -> str:
    """Load DATABASE_URL from environment / .env file."""
    try:
        from dotenv import load_dotenv
        env_path = pathlib.Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
    return os.environ.get("DATABASE_URL", "")


class DatabaseManager:
    """PostgreSQL manager for buchungen table."""

    def __init__(self):
        self._url = _load_database_url()

    # ── public helpers ────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Check if DATABASE_URL is set and psycopg2 is available."""
        if not self._url:
            return False
        try:
            import psycopg2  # noqa: F401
            return True
        except ImportError:
            return False

    # ── connection ────────────────────────────────────────────────────────

    def _connect(self):
        """Return a new psycopg2 connection or None."""
        if not self.is_configured():
            return None
        try:
            import psycopg2
            return psycopg2.connect(self._url)
        except Exception:
            return None

    # ── schema ────────────────────────────────────────────────────────────

    def init_db(self) -> bool:
        """Create the buchungen table if it does not exist. Returns True on success."""
        conn = self._connect()
        if conn is None:
            return False
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS buchungen (
                            id          SERIAL PRIMARY KEY,
                            datum       TEXT,
                            beleg       TEXT,
                            rechnung    TEXT,
                            beschreibung TEXT,
                            kt_soll     TEXT,
                            kt_haben    TEXT,
                            betrag_chf  NUMERIC,
                            mwst_code   TEXT,
                            art_betrag  TEXT,
                            mwst_pct    TEXT,
                            mwst_chf    NUMERIC,
                            ks3         TEXT,
                            source      TEXT,
                            created_at  TIMESTAMP DEFAULT NOW()
                        )
                    """)
            return True
        except Exception:
            return False
        finally:
            conn.close()

    # ── write ─────────────────────────────────────────────────────────────

    def save_buchungen(self, df: pd.DataFrame, source: str) -> bool:
        """Save a DataFrame of bookings. source = 'kontoauszug' or 'rechnung'.

        Returns True on success.
        """
        conn = self._connect()
        if conn is None:
            return False

        self.init_db()

        try:
            with conn:
                with conn.cursor() as cur:
                    for _, row in df.iterrows():
                        betrag = row.get("Betrag CHF", None)
                        try:
                            betrag = float(betrag) if betrag not in (None, "") else None
                        except (ValueError, TypeError):
                            betrag = None

                        mwst_chf = row.get("Gebuchte MwSt/USt CHF", None)
                        try:
                            mwst_chf = float(mwst_chf) if mwst_chf not in (None, "") else None
                        except (ValueError, TypeError):
                            mwst_chf = None

                        cur.execute(
                            """
                            INSERT INTO buchungen
                                (datum, beleg, rechnung, beschreibung, kt_soll, kt_haben,
                                 betrag_chf, mwst_code, art_betrag, mwst_pct, mwst_chf, ks3, source)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                str(row.get("Datum", "")),
                                str(row.get("Beleg", "")),
                                str(row.get("Rechnung", "")),
                                str(row.get("Beschreibung", "")),
                                str(row.get("KtSoll", "")),
                                str(row.get("KtHaben", "")),
                                betrag,
                                str(row.get("MwSt/USt-Code", "")),
                                str(row.get("Art Betrag", "")),
                                str(row.get("MwSt-%", "")),
                                mwst_chf,
                                str(row.get("KS3", "")),
                                source,
                            ),
                        )
            return True
        except Exception:
            return False
        finally:
            conn.close()

    # ── read ──────────────────────────────────────────────────────────────

    def load_buchungen(self, source: str | None = None, limit: int = 500) -> pd.DataFrame:
        """Load bookings back as DataFrame. Optionally filter by source."""
        conn = self._connect()
        if conn is None:
            return pd.DataFrame()
        try:
            with conn:
                with conn.cursor() as cur:
                    if source:
                        cur.execute(
                            "SELECT datum, beleg, rechnung, beschreibung, kt_soll, kt_haben, "
                            "betrag_chf, mwst_code, art_betrag, mwst_pct, mwst_chf, ks3, source, created_at "
                            "FROM buchungen WHERE source = %s ORDER BY created_at DESC LIMIT %s",
                            (source, limit),
                        )
                    else:
                        cur.execute(
                            "SELECT datum, beleg, rechnung, beschreibung, kt_soll, kt_haben, "
                            "betrag_chf, mwst_code, art_betrag, mwst_pct, mwst_chf, ks3, source, created_at "
                            "FROM buchungen ORDER BY created_at DESC LIMIT %s",
                            (limit,),
                        )
                    rows = cur.fetchall()
                    cols = [
                        "Datum", "Beleg", "Rechnung", "Beschreibung", "KtSoll", "KtHaben",
                        "Betrag CHF", "MwSt/USt-Code", "Art Betrag", "MwSt-%",
                        "Gebuchte MwSt/USt CHF", "KS3", "Source", "Erstellt",
                    ]
                    return pd.DataFrame(rows, columns=cols)
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

    # ── stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return counts per source, total, and latest date."""
        conn = self._connect()
        if conn is None:
            return {}
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM buchungen")
                    total = cur.fetchone()[0]

                    cur.execute(
                        "SELECT source, COUNT(*) FROM buchungen GROUP BY source"
                    )
                    per_source = {row[0]: row[1] for row in cur.fetchall()}

                    cur.execute(
                        "SELECT MAX(created_at) FROM buchungen"
                    )
                    latest = cur.fetchone()[0]

                    return {
                        "total": total,
                        "per_source": per_source,
                        "latest": str(latest) if latest else None,
                    }
        except Exception:
            return {}
        finally:
            conn.close()
