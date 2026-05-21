"""
conftest.py
Shared fixtures used across all test files.

"""

import os
import pytest

os.environ.setdefault("GOOGLE_CLIENT_ID",     "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI",  "http://localhost:8000/auth/callback")
os.environ.setdefault("SUPABASE_URL",         "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SESSION_SECRET",       "test-secret-key-that-is-long-enough")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Patching supabase client before database.py executes
mock_supabase = MagicMock()
with patch("supabase.create_client", return_value=mock_supabase):
    import database
    database.supabase = mock_supabase

    import crud
    crud.supabase = mock_supabase

    from main import app


# Fake data

FAKE_USER_DB = {
    "google_id":   "google-uid-123", #primary key
    "email":       "test@example.com",
    "name":        "Test User",
    "picture":     "https://example.com/photo.jpg",
    "login_count": 3,
    "created_at":  "2024-01-15T10:00:00+00:00",
}

FAKE_USERINFO = {
    "sub":     "google-uid-123",
    "email":   "test@example.com",
    "name":    "Test User",
    "picture": "https://example.com/photo.jpg",
}


# Fixtures

@pytest.fixture
def client():
    # Plain TestClient — no session, no auth

    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def mock_db():
    """
    Reset the mock_supabase builder chain before each test so that
    return values from one test don't bleed into the next.
    The chain used in crud.py is:
        supabase.table("users").select/insert/update/delete
            .[...filters...].execute()
    Made every link return the same mock so the chain always resolves.
    """
    mock_supabase.reset_mock()

    chain = MagicMock()
    mock_supabase.table.return_value = chain
    chain.select.return_value  = chain
    chain.insert.return_value  = chain
    chain.update.return_value  = chain
    chain.delete.return_value  = chain
    chain.eq.return_value      = chain
    chain.maybe_single.return_value = chain

    return chain


@pytest.fixture
def authenticated_client(client, mock_db):
    """
    TestClient with a valid signed session cookie containing a logged-in user.
    Use this for any test that requires the user to already be signed in.
    """
    # Set the session directly via the session middleware.
    with client.session_transaction() as session:
        session["user"] = {
            "google_id":   FAKE_USER_DB["google_id"],
            "name":        FAKE_USER_DB["name"],
            "email":       FAKE_USER_DB["email"],
            "picture":     FAKE_USER_DB["picture"],
            "login_count": FAKE_USER_DB["login_count"],
        }
    return client
