from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

def configure_sentry(dsn: str | None, environment: str = "production") -> None:
    if not dsn:
        logger.info("Sentry DSN not configured; error tracking disabled.")
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    logger.info("Sentry error tracking initialized.")