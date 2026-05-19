"""
database.py
-----------
Single Supabase client used across the whole app.
All DB operations go through the `supabase` object exported here.

Supabase table expected (run this SQL in Supabase SQL Editor):

    CREATE TABLE users (
        id          BIGSERIAL PRIMARY KEY,
        google_id   TEXT UNIQUE NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        name        TEXT,
        picture     TEXT,
        login_count INTEGER NOT NULL DEFAULT 0,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
