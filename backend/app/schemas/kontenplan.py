"""Kontenplan schemas."""

from pydantic import BaseModel


class KontoEntry(BaseModel):
    konto_nr: str
    beschreibung: str


class KontoDefaultEntry(BaseModel):
    konto_soll: str
    konto_haben: str = "1020"
    mwst_code: str = ""
    mwst_pct: str = ""


class KontenplanResponse(BaseModel):
    """Account number → description, as the Kontenplan editor reads it."""

    kontenplan: dict[str, str]


class KontenplanSaved(BaseModel):
    status: str
    count: int


class KontoDefaultOut(BaseModel):
    """Default counter-account and VAT for one debit account.

    The keys are the Banana column names the import/export speak, so they stay
    capitalised on the wire.
    """

    KontoHaben: str
    MwStCode: str
    MwStUStProz: str


class KontoDefaultsResponse(BaseModel):
    defaults: dict[str, KontoDefaultOut]


# --- B-20: der Import-Assistent ---------------------------------------------


class KontenplanImportZeile(BaseModel):
    """Eine Zeile der hochgeladenen Datei, wie der Assistent sie liest."""

    konto: str
    bezeichnung: str
    #: "neu" | "geaendert" | "unveraendert" | "ungueltig"
    status: str
    #: Nur bei "geaendert": was heute im Mandanten steht.
    bisher: str = ""
    #: Nur bei "ungueltig": warum.
    grund: str = ""
    #: Zeilennummer in der Datei, damit der Nutzer sie dort wiederfindet.
    quelle: int = 0


class KontenplanImportVorschau(BaseModel):
    """Was ein Import tun *würde*. Es wird nichts geschrieben.

    `entfaellt` ist der Satz, der vor dem Klick zählt: diese Konten hat der
    Mandant und die Datei nennt sie nicht, also verschwinden sie im Modus
    "ersetzen".
    """

    zeilen: list[KontenplanImportZeile]
    entfaellt: list[str]
    spalte_konto: str
    spalte_bezeichnung: str
    zaehler: dict[str, int]


class KontenplanImportErgebnis(BaseModel):
    status: str
    modus: str
    #: Konten im Kontenplan nach dem Import.
    count: int
    neu: int
    geaendert: int
    entfernt: int
