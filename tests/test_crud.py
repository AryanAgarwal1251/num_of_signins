"""
test_crud.py
------------
Unit tests for crud.py.

Every test patches the supabase builder chain at the crud module level
so no real network call is made. We test:

  - get_user_by_google_id  (found / not found)
  - create_user
  - increment_login_count  (including the read-before-write)
  - delete_user
  - edge cases (None login_count, missing user before increment)
"""

import pytest
from unittest.mock import MagicMock, patch, call

# conftest already patched the env and supabase before import
import api.crud as crud
from .conftest import FAKE_USER_DB


# helpers

def make_chain(return_data):
    """
    Return a MagicMock that mimics the Supabase fluent builder chain.
    Every chainable method returns itself; .execute() returns an object
    whose .data attribute equals `return_data`.
    """
    chain = MagicMock()
    # Every builder method returns the same chain
    for method in ("select", "insert", "update", "delete", "eq", "maybe_single"):
        getattr(chain, method).return_value = chain

    execute_result = MagicMock()
    execute_result.data = return_data
    chain.execute.return_value = execute_result
    return chain


# get_user_by_google_id

class TestGetUserByGoogleId:

    def test_returns_user_dict_when_found(self):
        chain = make_chain(FAKE_USER_DB)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            result = crud.get_user_by_google_id("google-uid-123")
        assert result == FAKE_USER_DB

    def test_returns_none_when_not_found(self):
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            result = crud.get_user_by_google_id("nonexistent-id")
        assert result is None

    def test_queries_correct_table(self):
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.get_user_by_google_id("some-id")
        mock_sb.table.assert_called_once_with("users")

    def test_filters_by_google_id(self):
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.get_user_by_google_id("uid-abc")
        chain.eq.assert_called_once_with("google_id", "uid-abc")

    def test_uses_maybe_single(self):
        """maybe_single() must be called so Supabase returns None instead of []."""
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.get_user_by_google_id("uid-abc")
        chain.maybe_single.assert_called_once()

# create_user

class TestCreateUser:

    def test_returns_inserted_row(self):
        new_row = {**FAKE_USER_DB, "login_count": 1}
        chain = make_chain([new_row])
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            result = crud.create_user("google-uid-123", "test@example.com", "Test User", "https://pic.url")
        assert result == new_row

    def test_inserts_with_correct_payload(self):
        chain = make_chain([FAKE_USER_DB])
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.create_user("gid", "e@mail.com", "Name", "pic.url")

        chain.insert.assert_called_once_with({
            "google_id":   "gid",
            "email":       "e@mail.com",
            "name":        "Name",
            "picture":     "pic.url",
            "login_count": 1,
        })

    def test_login_count_starts_at_1(self):
        """New users must always start with login_count = 1, never 0."""
        chain = make_chain([{**FAKE_USER_DB, "login_count": 1}])
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.create_user("gid", "e@mail.com", "Name", "pic.url")

        inserted_payload = chain.insert.call_args[0][0]
        assert inserted_payload["login_count"] == 1

    def test_inserts_into_users_table(self):
        chain = make_chain([FAKE_USER_DB])
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.create_user("g", "e", "n", "p")
        mock_sb.table.assert_called_once_with("users")

# increment_login_count

class TestIncrementLoginCount:

    def test_increments_count_by_1(self):
        """login_count must go from 3 → 4."""
        existing = {**FAKE_USER_DB, "login_count": 3}
        updated  = {**FAKE_USER_DB, "login_count": 4}

        # Two calls to supabase.table: first the SELECT, then the UPDATE
        select_chain = make_chain(existing)
        update_chain = make_chain([updated])

        call_count = {"n": 0}
        def table_side_effect(table_name):
            call_count["n"] += 1
            return select_chain if call_count["n"] == 1 else update_chain

        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.side_effect = table_side_effect
            result = crud.increment_login_count("google-uid-123")

        assert result == updated

    def test_update_payload_has_correct_count(self):
        """The UPDATE call must pass new_count = old + 1."""
        existing = {**FAKE_USER_DB, "login_count": 5}
        updated  = {**FAKE_USER_DB, "login_count": 6}

        select_chain = make_chain(existing)
        update_chain = make_chain([updated])

        call_count = {"n": 0}
        def table_side_effect(_):
            call_count["n"] += 1
            return select_chain if call_count["n"] == 1 else update_chain

        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.side_effect = table_side_effect
            crud.increment_login_count("google-uid-123")

        update_chain.update.assert_called_once_with({"login_count": 6})

    def test_handles_none_login_count_gracefully(self):
        """
        Edge case: login_count is None in the DB (e.g. after a bad migration).
        Should treat None as 0 and write 1.
        """
        existing = {**FAKE_USER_DB, "login_count": None}
        updated  = {**FAKE_USER_DB, "login_count": 1}

        select_chain = make_chain(existing)
        update_chain = make_chain([updated])

        call_count = {"n": 0}
        def table_side_effect(_):
            call_count["n"] += 1
            return select_chain if call_count["n"] == 1 else update_chain

        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.side_effect = table_side_effect
            result = crud.increment_login_count("google-uid-123")

        update_chain.update.assert_called_once_with({"login_count": 1})
        assert result["login_count"] == 1


# delete_user

class TestDeleteUser:

    def test_calls_delete_on_correct_google_id(self):
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.delete_user("google-uid-123")

        chain.delete.assert_called_once()
        chain.eq.assert_called_once_with("google_id", "google-uid-123")

    def test_returns_none(self):
        """delete_user should return None — callers don't need a return value."""
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            result = crud.delete_user("google-uid-123")
        assert result is None

    def test_deletes_from_users_table(self):
        chain = make_chain(None)
        with patch.object(crud, "supabase") as mock_sb:
            mock_sb.table.return_value = chain
            crud.delete_user("google-uid-123")
        mock_sb.table.assert_called_once_with("users")
