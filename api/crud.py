"""
crud.py
All database read/write operations.
Uses the Supabase Python client directly and no SQLAlchemy needed.
"""

from api.database import supabase


def get_user_by_google_id(google_id: str) -> dict | None:

    if not google_id:
        return None

    if not isinstance(google_id, str):
        raise ValueError("google_id must be a string")
        
    try:
        response = (
            supabase.table("users")
            .select("*")
            .eq("google_id", google_id)
            .maybe_single()
            .execute()
        )

        return response.data

    except Exception as e:
        print(f"Supabase error: {e}")
        return None


def create_user(google_id: str, email: str, name: str, picture: str) -> dict:
    """Insert a new user with login_count = 1 and return the row."""
    result = (
        supabase.table("users")
        .insert({
            "google_id": google_id,
            "email": email,
            "name": name,
            "picture": picture,
            "login_count": 1,
        })
        .execute()
    )
    return result.data[0]


def increment_login_count(google_id: str) -> dict:
    """Bump login_count by 1 and return the updated row."""
    # Read current count first
    user = get_user_by_google_id(google_id)
    new_count = (user["login_count"] or 0) + 1

    result = (
        supabase.table("users")
        .update({"login_count": new_count})
        .eq("google_id", google_id)
        .execute()
    )
    return result.data[0]


def delete_user(google_id: str) -> None:
    """Permanently remove a user row."""
    supabase.table("users").delete().eq("google_id", google_id).execute()
