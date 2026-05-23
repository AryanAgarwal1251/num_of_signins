"""
test_auth.py
Unit tests for auth.py.

Tests:
  - get_google_auth_url - URL construction
"""

import pytest
import httpx
import os
from unittest.mock import patch, AsyncMock, MagicMock
from urllib.parse import urlparse, parse_qs

import api.auth as auth
from .conftest import FAKE_USERINFO

# get_google_auth_url

class TestGetGoogleAuthUrl:

    def test_returns_google_auth_domain(self):
        url = auth.get_google_auth_url("some-state")
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth") #starting google oauth url is correct

    def test_contains_client_id(self):
        url = auth.get_google_auth_url("some-state")
        assert "client_id=test-client-id" in url #checking query params

    def test_contains_response_type_code(self):
        url = auth.get_google_auth_url("some-state")
        assert "response_type=code" in url #query param for response type

    def test_contains_state(self):
        url = auth.get_google_auth_url("my-unique-state")
        assert "state=my-unique-state" in url # security mechanism

    def test_contains_redirect_uri(self):
        url = auth.get_google_auth_url("some-state")
        assert "redirect_uri=" f"{os.environ.get("GOOGLE_REDIRECT_URI")}" in url # redirect uri checking

    def test_contains_openid_scope(self):
        url = auth.get_google_auth_url("some-state")
        assert "openid" in url

    def test_contains_email_scope(self):
        url = auth.get_google_auth_url("some-state")
        assert "email" in url

    def test_contains_profile_scope(self):
        url = auth.get_google_auth_url("some-state")
        assert "profile" in url
    


    