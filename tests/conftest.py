"""
Pytest fixtures for API tests. Shared base URL; optional admin JWT for admin tests.
"""
import os

import pytest


def _base_url():
    return os.environ.get("GEOMAPPER_URL", "http://127.0.0.1:8080").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    """Base URL of the running backend (e.g. http://127.0.0.1:8080). Set GEOMAPPER_URL to override."""
    return _base_url()


@pytest.fixture(scope="session")
def admin_jwt():
    """
    Optional admin JWT for admin API tests. Set GEOMAPPER_ADMIN_JWT to a valid Supabase
    access_token for a user with role=admin. If unset, admin tests are skipped.
    """
    return os.environ.get("GEOMAPPER_ADMIN_JWT")


@pytest.fixture(scope="session")
def driver_id():
    """Optional driver profile ID for Phase 6 batch tests. Set GEOMAPPER_DRIVER_ID."""
    return os.environ.get("GEOMAPPER_DRIVER_ID")
