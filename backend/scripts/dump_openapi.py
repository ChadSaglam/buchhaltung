"""Dump the FastAPI OpenAPI schema to stdout without starting a server.

Used by ``scripts/gen-api-types.sh`` to keep the frontend's types in lockstep
with the backend. Run from the ``backend/`` directory.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The schema must be generatable without a database or any secret material.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "openapi-generation-secret-not-used-at-runtime")

from app.main import application

if __name__ == "__main__":
    json.dump(application.openapi(), sys.stdout, indent=2, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
