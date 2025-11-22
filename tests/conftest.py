from __future__ import annotations

import os
from pathlib import Path


TEST_CREDENTIALS = Path(__file__).resolve().parent / "data" / "runtime_credentials.json"

os.environ.setdefault("JWT_SIGNING_KEY", "test-signing-key")
os.environ.setdefault("ADMIN_CREDENTIALS_PATH", str(TEST_CREDENTIALS))
os.environ.setdefault("ADMIN_JWT_TTL_HOURS", "168")
