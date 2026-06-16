"""Scanner-config service — tenant-scoped get-or-create and update."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scanner_config import ScannerConfig


class ScannerConfigService:
    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db

    async def get_or_create(self) -> ScannerConfig:
        result = await self.db.execute(
            select(ScannerConfig).where(ScannerConfig.tenant_id == self.tenant_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            config = ScannerConfig(tenant_id=self.tenant_id)
            self.db.add(config)
            await self.db.flush()
        return config

    async def update(self, fields: dict) -> ScannerConfig:
        config = await self.get_or_create()
        for key, value in fields.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
        await self.db.flush()
        return config