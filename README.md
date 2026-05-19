# num_of_signs

A minimal FastAPI app that counts how many times each user has signed in via Google OAuth.
User data is stored in Supabase Postgres.

---

## Project Structure

```
num_of_signs/
├── main.py          # FastAPI app + all routes
├── auth.py          # Google OAuth flow (redirect → callback → userinfo)
├── crud.py          # All database operations (Supabase client)
├── database.py      # Supabase client initialisation
├── templates/
│   ├── login.html   # Sign-in page
│   └── dashboard.html  # Post-login page showing sign-in count
├── requirements.txt
└── .env.example     # Copy to .env and fill in your values
```

---

## 1. Supabase Setup

In your Supabase project, open the **SQL Editor** and run:

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    google_id   TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    picture     TEXT,
    login_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

Copy the **Project URL** and **service_role** key from:
`Project Settings → API`

---

## 2. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a project (or use an existing one)
3. Enable the **Google+ API** (or **People API**)
4. Create **OAuth 2.0 Client ID** → Web application
5. Add to **Authorised Redirect URIs**:
   ```
   http://localhost:8000/auth/callback
   ```
6. Copy the **Client ID** and **Client Secret**

---

## 3. Local Setup

```bash
# Clone / enter the project folder
cd num_of_signs

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in all four values

# Run the app
uvicorn main:app --reload
```

Open http://localhost:8000 in your browser.

---

## 4. How it Works

| Step | What happens |
|------|-------------|
| User visits `/` | Shown login page |
| Clicks "Continue with Google" | Browser is redirected to Google consent screen |
| User grants permission | Google redirects to `/auth/callback?code=...` |
| First visit | New row inserted in `users` with `login_count = 1` |
| Return visit | Existing row's `login_count` incremented by 1 |
| Dashboard | Shows profile picture, name, email, and total sign-in count |
| Sign Out | Session cleared, user returned to login page |
| Delete Account | Row deleted from DB, session cleared |

---

## Environment Variables

| Variable | Where to find it |
|----------|-----------------|
| `GOOGLE_CLIENT_ID` | Google Cloud Console → Credentials |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console → Credentials |
| `GOOGLE_REDIRECT_URI` | Must match what you registered; `http://localhost:8000/auth/callback` for local dev |
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API → service_role (secret) key |
| `SESSION_SECRET` | Any long random string — run `python -c "import secrets; print(secrets.token_hex(32))"` |
