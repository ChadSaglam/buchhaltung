"""SQLAlchemy models for Kontenplan and KontoDefaults."""
from sqlalchemy import Column, Integer, String, ForeignKey
from app.models.base import Base


class Konto(Base):
    __tablename__ = "kontenplan"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    konto_nr = Column(String, nullable=False)
    beschreibung = Column(String, nullable=False, default="")

    # Aliases for router compatibility
    @property
    def konto(self) -> str:
        return self.konto_nr

    @property
    def bezeichnung(self) -> str:
        return self.beschreibung


# Alias so routers can do: from app.models.kontenplan import Kontenplan
Kontenplan = Konto


class KontoDefault(Base):
    __tablename__ = "konto_defaults"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    konto_soll = Column(String, nullable=False)
    konto_haben = Column(String, nullable=False, default="1020")
    mwst_code = Column(String, nullable=False, default="")
    mwst_pct = Column(String, nullable=False, default="")
