"""
Entry point. All routes live here — the app is small enough
that separate route files would only add complexity.

Run:
    uvicorn main:app --reload
"""

import os
import secrets
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import crud
from auth import get_google_auth_url, exchange_code_for_userinfo

load_dotenv()

app = FastAPI()

# Session middleware (cookie-backed, server-signed)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    session_cookie="session",
    max_age=60 * 60,  # 1 hour
    https_only=True,       # set True in production behind HTTPS
)

templates = Jinja2Templates(directory="templates")


# Helpers

def current_user(request: Request) -> dict | None:
    """Return the session user dict, or None if not logged in."""
    return request.session.get("user")


# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page: redirect to dashboard if logged in, else show login."""
    if current_user(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(request = request, name = "login.html", context = {})


@app.get("/auth/login")
async def auth_login(request: Request):
    """Redirect the browser to Google's consent screen."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(get_google_auth_url(state))


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """
    Google redirects here after the user grants/denies permission.
    - Exchange code -> access token -> userinfo
    - Upsert user in DB (create on first visit, increment count on return)
    - Store minimal user info in session
    """
    if error:
        return RedirectResponse(f"/?error={error}")

    # CSRF check
    if state != request.session.pop("oauth_state", None):
        return RedirectResponse("/?error=state_mismatch")

    try:
        userinfo = await exchange_code_for_userinfo(code)
    except Exception:
        return RedirectResponse("/?error=token_exchange_failed")

    google_id = userinfo["sub"]
    email     = userinfo.get("email", "")
    name      = userinfo.get("name", "")
    picture   = userinfo.get("picture", "")

    # Upsert: create new user OR increment existing user's counter
    existing = crud.get_user_by_google_id(google_id)

    if existing is None:
        user = crud.create_user(google_id, email, name, picture)
    else:
        user = crud.increment_login_count(google_id)

    # Store only what the templates need — keep session lean
    request.session["user"] = {
        "google_id":   google_id,
        "name":        name,
        "email":       email,
        "picture":     picture,
        "login_count": user["login_count"],
    }

    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main page shown after login."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/")

    # Re-fetch from DB so the count is always fresh
    db_user = crud.get_user_by_google_id(user["google_id"])
    if not db_user:
        request.session.clear()
        return RedirectResponse("/")

    return templates.TemplateResponse(name="dashboard.html",
        request=request,
        context={
            "user": db_user,
        })


@app.post("/auth/logout")
async def logout(request: Request):
    """Clear the session and return to login page."""
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.post("/account/delete")
async def delete_account(request: Request):
    """Permanently delete the user's account and all their data."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/", status_code=303)

    crud.delete_user(user["google_id"])
    request.session.clear()
    return RedirectResponse("/?deleted=1", status_code=303)
