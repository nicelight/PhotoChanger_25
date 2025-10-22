"""Pytest configuration for schema-destructive database tests."""

import pytest

pytestmark = pytest.mark.db_sensitive
