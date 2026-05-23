"""
test_routes.py
--------------
Tests for every route in main.py.

Sections
--------
1.  GET /                  – index / landing page
2.  GET /auth/login        – OAuth redirect initiation
3.  GET /auth/callback     – OAuth callback (happy path + all error branches)
4.  GET /dashboard         – protected dashboard page
5.  POST /auth/logout      – logout
6.  POST /account/delete   – account deletion
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from .conftest import FAKE_USER_DB, FAKE_USERINFO

# 1.  GET /  – Landing page

class TestIndex:

    def test_shows_login_page_when_not_authenticated(self, client):
        """Unauthenticated visitor should see the login page (200)."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Continue with Google" in response.text

    def test_redirects_to_dashboard_when_authenticated(self, authenticated_client, mock_db):
        """Authenticated user hitting / should be sent to /dashboard."""
        response = authenticated_client.get("/")
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/dashboard"

    def test_login_page_shows_error_on_state_mismatch(self, client):
        """?error=state_mismatch query param should surface an error message."""
        response = client.get("/?error=state_mismatch")
        assert response.status_code == 200
        assert "Security check failed" in response.text

    def test_login_page_shows_error_on_token_exchange_failure(self, client):
        """?error=token_exchange_failed should show a generic error."""
        response = client.get("/?error=token_exchange_failed")
        assert response.status_code == 200
        assert "Could not complete sign-in" in response.text

    def test_login_page_shows_generic_error_for_unknown_error(self, client):
        """Any other ?error value should show the generic cancellation message."""
        response = client.get("/?error=access_denied")
        assert response.status_code == 200
        assert "cancelled or failed" in response.text

    def test_login_page_shows_deleted_message(self, client):
        """?deleted=1 should show an account-deleted confirmation."""
        response = client.get("/?deleted=1")
        assert response.status_code == 200
        assert "account has been deleted" in response.text


# 2.  GET /auth/login – OAuth redirect

class TestAuthLogin:

    def test_redirects_to_google(self, client):
        """Should redirect to accounts.google.com."""
        response = client.get("/auth/login")
        assert response.status_code in (302, 307)
        assert "accounts.google.com" in response.headers["location"]

    def test_redirect_url_contains_required_params(self, client):
        """Google redirect URL must carry client_id, scope, response_type, state."""
        response = client.get("/auth/login")
        location = response.headers["location"]
        assert "client_id=test-client-id" in location
        assert "response_type=code" in location
        assert "openid" in location       # part of scope
        assert "state=" in location

    def test_state_stored_in_session(self, client):
        """The state token must be written to the session for CSRF protection."""
        client.get("/auth/login")
        with client.session_transaction() as session:
            assert "oauth_state" in session
            assert len(session["oauth_state"]) > 8

    def test_state_is_random_each_call(self, client):
        """Each call must produce a different state value."""
        client.get("/auth/login")
        with client.session_transaction() as session:
            state1 = session["oauth_state"]

        client.get("/auth/login")
        with client.session_transaction() as session:
            state2 = session["oauth_state"]

        assert state1 != state2


# 3.  GET /auth/callback – OAuth callback

class TestAuthCallback:

    # helpers

    def _set_state(self, client, state: str):
        """Pre-load the session with the expected OAuth state."""
        with client.session_transaction() as session:
            session["oauth_state"] = state

    # error parameter

    def test_error_param_redirects_to_root(self, client):
        """If Google sends ?error=access_denied we redirect to /?error=..."""
        response = client.get("/auth/callback?error=access_denied")
        assert response.status_code in (302, 307)
        assert "error=access_denied" in response.headers["location"]

    # CSRF / state mismatch 

    def test_missing_state_in_session_causes_state_mismatch(self, client):
        """No session state → redirect with state_mismatch error."""
        response = client.get("/auth/callback?code=abc&state=wrong")
        assert response.status_code in (302, 307)
        assert "state_mismatch" in response.headers["location"]

    def test_wrong_state_causes_state_mismatch(self, client):
        """State in URL differs from session state → state_mismatch."""
        self._set_state(client, "correct-state")
        response = client.get("/auth/callback?code=abc&state=wrong-state")
        assert response.status_code in (302, 307)
        assert "state_mismatch" in response.headers["location"]

    def test_state_consumed_after_use(self, client):
        """oauth_state must be removed from session after the callback."""
        self._set_state(client, "my-state")
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(return_value=FAKE_USERINFO)), \
             patch("main.crud.get_user_by_google_id", return_value=None), \
             patch("main.crud.create_user", return_value={**FAKE_USER_DB, "login_count": 1}):
            client.get("/auth/callback?code=abc&state=my-state")

        with client.session_transaction() as session:
            assert "oauth_state" not in session

    # exchange failure

    def test_exchange_failure_redirects_with_error(self, client):
        """If exchange_code_for_userinfo raises, send token_exchange_failed."""
        self._set_state(client, "valid-state")
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(side_effect=Exception("network error"))):
            response = client.get("/auth/callback?code=bad&state=valid-state")
        assert response.status_code in (302, 307)
        assert "token_exchange_failed" in response.headers["location"]

    # new user (happy path) 

    def test_new_user_is_created_in_db(self, client):
        """First-time sign-in must call crud.create_user, not increment."""
        self._set_state(client, "s1")
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(return_value=FAKE_USERINFO)) as mock_exchange, \
             patch("main.crud.get_user_by_google_id", return_value=None) as mock_get, \
             patch("main.crud.create_user", return_value={**FAKE_USER_DB, "login_count": 1}) as mock_create, \
             patch("main.crud.increment_login_count") as mock_inc:

            response = client.get("/auth/callback?code=authcode&state=s1")

        mock_create.assert_called_once_with(
            FAKE_USERINFO["sub"],
            FAKE_USERINFO["email"],
            FAKE_USERINFO["name"],
            FAKE_USERINFO["picture"],
        )
        mock_inc.assert_not_called()
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/dashboard"

    def test_new_user_session_contains_correct_data(self, client):
        """Session must store google_id, email, name, picture, login_count."""
        self._set_state(client, "s2")
        created_user = {**FAKE_USER_DB, "login_count": 1}
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(return_value=FAKE_USERINFO)), \
             patch("main.crud.get_user_by_google_id", return_value=None), \
             patch("main.crud.create_user", return_value=created_user):
            client.get("/auth/callback?code=authcode&state=s2")

        with client.session_transaction() as session:
            user = session["user"]
            assert user["google_id"]   == FAKE_USERINFO["sub"]
            assert user["email"]       == FAKE_USERINFO["email"]
            assert user["name"]        == FAKE_USERINFO["name"]
            assert user["login_count"] == 1

    # returning user

    def test_returning_user_increments_count(self, client):
        """Returning user must call crud.increment_login_count, not create_user."""
        self._set_state(client, "s3")
        updated = {**FAKE_USER_DB, "login_count": 4}
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(return_value=FAKE_USERINFO)), \
             patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB), \
             patch("main.crud.increment_login_count", return_value=updated) as mock_inc, \
             patch("main.crud.create_user") as mock_create:

            client.get("/auth/callback?code=authcode&state=s3")

        mock_inc.assert_called_once_with(FAKE_USER_DB["google_id"])
        mock_create.assert_not_called()

    def test_returning_user_session_has_updated_count(self, client):
        """Session login_count must reflect the post-increment value."""
        self._set_state(client, "s4")
        updated = {**FAKE_USER_DB, "login_count": 10}
        with patch("main.exchange_code_for_userinfo", new=AsyncMock(return_value=FAKE_USERINFO)), \
             patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB), \
             patch("main.crud.increment_login_count", return_value=updated):
            client.get("/auth/callback?code=authcode&state=s4")

        with client.session_transaction() as session:
            assert session["user"]["login_count"] == 10

# 4.  GET /dashboard – protected page

class TestDashboard:

    def test_unauthenticated_redirects_to_root(self, client):
        """No session → redirect to /."""
        response = client.get("/dashboard")
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/"

    def test_authenticated_shows_dashboard(self, authenticated_client):
        """Logged-in user must see their dashboard (200 with their name)."""
        with patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB):
            response = authenticated_client.get("/dashboard")
        assert response.status_code == 200
        assert FAKE_USER_DB["name"] in response.text

    def test_dashboard_shows_login_count(self, authenticated_client):
        """The sign-in counter must be rendered on the dashboard."""
        with patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB):
            response = authenticated_client.get("/dashboard")
        assert str(FAKE_USER_DB["login_count"]) in response.text

    def test_dashboard_shows_email(self, authenticated_client):
        """User email must appear on the dashboard."""
        with patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB):
            response = authenticated_client.get("/dashboard")
        assert FAKE_USER_DB["email"] in response.text

    def test_dashboard_re_fetches_from_db(self, authenticated_client):
        """Dashboard must call get_user_by_google_id on every load (fresh count)."""
        with patch("main.crud.get_user_by_google_id", return_value=FAKE_USER_DB) as mock_get:
            authenticated_client.get("/dashboard")
        mock_get.assert_called_once_with(FAKE_USER_DB["google_id"])

    def test_stale_session_user_not_in_db_redirects_to_root(self, authenticated_client):
        """
        Edge case: user deleted from DB externally but session still active.
        Should clear session and redirect to /.
        """
        with patch("main.crud.get_user_by_google_id", return_value=None):
            response = authenticated_client.get("/dashboard")
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/"

    def test_stale_session_clears_session(self, authenticated_client):
        """Stale session (user not in DB) must be cleared."""
        with patch("main.crud.get_user_by_google_id", return_value=None):
            authenticated_client.get("/dashboard")
        with authenticated_client.session_transaction() as session:
            assert "user" not in session


# 5.  POST /auth/logout

class TestLogout:

    def test_logout_redirects_to_root(self, authenticated_client):
        """POST /auth/logout must redirect to /."""
        response = authenticated_client.post("/auth/logout")
        assert response.status_code in (302, 303, 307)
        assert response.headers["location"] == "/"

    def test_logout_clears_session(self, authenticated_client):
        """Session must be empty after logout."""
        authenticated_client.post("/auth/logout")
        with authenticated_client.session_transaction() as session:
            assert "user" not in session

    def test_logout_when_not_logged_in_still_redirects(self, client):
        """Logging out without a session should still redirect cleanly to /."""
        response = client.post("/auth/logout")
        assert response.status_code in (302, 303, 307)
        assert response.headers["location"] == "/"


# 6.  POST /account/delete

class TestDeleteAccount:

    def test_unauthenticated_delete_redirects_to_root(self, client):
        """DELETE without a session -> redirect to /."""
        response = client.post("/account/delete")
        assert response.status_code in (302, 303, 307)
        assert response.headers["location"] == "/"

    def test_authenticated_delete_calls_crud(self, authenticated_client):
        """crud.delete_user must be called with the user's google_id."""
        with patch("main.crud.delete_user") as mock_del:
            authenticated_client.post("/account/delete")
        mock_del.assert_called_once_with(FAKE_USER_DB["google_id"])

    def test_authenticated_delete_clears_session(self, authenticated_client):
        """Session must be empty after account deletion."""
        with patch("main.crud.delete_user"):
            authenticated_client.post("/account/delete")
        with authenticated_client.session_transaction() as session:
            assert "user" not in session

    def test_authenticated_delete_redirects_with_deleted_flag(self, authenticated_client):
        """After deletion, redirect to /?deleted=1."""
        with patch("main.crud.delete_user"):
            response = authenticated_client.post("/account/delete")
        assert response.status_code in (302, 303, 307)
        assert "deleted=1" in response.headers["location"]
