"""Lohn (B-72)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_ZULAGEN = 1_000_000.0
MAX_MONATSLOHN = 1_000_000.0
MAX_SATZ = 100.0


class LohnSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ahv_satz_an: float
    alv_satz_an: float
    alv_jahresgrenze: float
    uvg_bu_satz: float | None = None
    uvg_nbu_satz: float | None = None
    uvgz_satz_an: float | None = None
    uvgz_satz_ag: float | None = None
    ktg_satz_an: float | None = None
    ktg_satz_ag: float | None = None
    fak_satz: float | None = None
    verwaltungskosten_satz: float | None = None
    konto_lohnaufwand: str
    konto_sozialversicherung: str
    konto_verbindlichkeit: str
    konto_bank: str
    #: Compulsory rates that are not on file yet; while this is non-empty no
    #: payslip can be issued.
    fehlt: list[str] = []
    bereit: bool = False


class LohnSettingsUpdate(BaseModel):
    ahv_satz_an: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    alv_satz_an: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    alv_jahresgrenze: float | None = Field(default=None, ge=0)
    uvg_bu_satz: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    uvg_nbu_satz: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    uvgz_satz_an: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    uvgz_satz_ag: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    ktg_satz_an: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    ktg_satz_ag: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    fak_satz: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    verwaltungskosten_satz: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    konto_lohnaufwand: str | None = Field(default=None, max_length=20)
    konto_sozialversicherung: str | None = Field(default=None, max_length=20)
    konto_verbindlichkeit: str | None = Field(default=None, max_length=20)
    konto_bank: str | None = Field(default=None, max_length=20)


class MitarbeiterBase(BaseModel):
    vorname: str = Field(default="", max_length=100)
    name: str = Field(default="", max_length=100)
    ahv_nummer: str = Field(default="", max_length=20)
    geburtsdatum: date | None = None
    eintritt: date | None = None
    austritt: date | None = None
    pensum: float = Field(default=100.0, ge=0, le=100)
    monatslohn: float = Field(default=0.0, ge=0, le=MAX_MONATSLOHN)
    dreizehnter: bool = False
    kinder: int = Field(default=0, ge=0, le=20)
    kanton: str = Field(default="", max_length=2)
    quellensteuer: bool = False
    quellensteuer_satz: float | None = Field(default=None, ge=0, le=MAX_SATZ)
    quellensteuer_tarif: str = Field(default="", max_length=10)
    bvg_an_monat: float | None = Field(default=None, ge=0, le=MAX_MONATSLOHN)
    bvg_ag_monat: float | None = Field(default=None, ge=0, le=MAX_MONATSLOHN)
    iban: str = Field(default="", max_length=34)
    email: str = Field(default="", max_length=255)


class MitarbeiterCreate(MitarbeiterBase):
    pass


class MitarbeiterUpdate(MitarbeiterBase):
    pass


class MitarbeiterOut(MitarbeiterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anzeige_name: str = ""


class AbzugOut(BaseModel):
    label: str
    satz: float
    basis: float
    betrag: float


class LohnlaufOut(BaseModel):
    """A payslip, issued or only previewed — the shape is the same either way."""

    mitarbeiter_id: int
    mitarbeiter: str
    jahr: int
    monat: int
    periode: str
    #: 1.0 for a whole month; less when the employee joined or left mid-month.
    anteil: float
    grundlohn: float
    dreizehnter: float
    zulagen: float
    brutto: float
    abzuege: list[AbzugOut] = []
    abzuege_total: float
    netto: float
    arbeitgeber: list[AbzugOut] = []
    ag_total: float
    #: Set only once the payslip exists as a row.
    abrechnung_id: int | None = None
    abgerechnet_am: datetime | None = None


class LohnlaufRequest(BaseModel):
    mitarbeiter_id: int
    jahr: int = Field(ge=2000, le=2100)
    monat: int = Field(ge=1, le=12)
    zulagen: float = Field(default=0.0, ge=0, le=MAX_ZULAGEN)
    dreizehnter: bool = False


class AbrechnungListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mitarbeiter_id: int
    jahr: int
    monat: int
    periode: str
    brutto: float
    abzuege: float
    netto: float
    ag_total: float
    abgerechnet_am: datetime | None = None


class AbrechnungListResponse(BaseModel):
    eintraege: list[AbrechnungListItem] = []
    brutto_total: float = 0.0
    netto_total: float = 0.0
    ag_total: float = 0.0


class BuchungOut(BaseModel):
    datum: str
    beschreibung: str
    betrag: float
    kt_soll: str
    kt_haben: str


class AbrechnenResponse(BaseModel):
    abrechnung: LohnlaufOut
    buchungen: list[BuchungOut] = []
