"""
auth.py
-------
Google OAuth 2.0 using Authlib's AsyncOAuth2Client.

Flow:
  1. /auth/login        → redirect to Google consent screen
  2. Google redirects   → /auth/callback?code=...&state=...
  3. Exchange code for tokens, fetch userinfo from Google
  4. Upsert user in DB, store google_id in session
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REDIRECT_URI  = os.environ["GOOGLE_REDIRECT_URI"]

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = "openid email profile"


def get_google_auth_url(state: str) -> str:
    """Build the Google consent-screen URL."""
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",   # always show account picker
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code_for_userinfo(code: str) -> dict:
    """
    Exchange the authorization code for tokens, then fetch Google userinfo.
    Returns a dict with: sub, email, name, picture.
    """
    async with httpx.AsyncClient() as client:
        # 1. Get access token
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # 2. Fetch user profile
        userinfo_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
        # keys: sub, email, name, picture, email_verified, …
