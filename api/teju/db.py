"""SQLite storage. Plain SQL kept portable so a move to Postgres only changes the driver and placeholders."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "teju.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  pw_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  lang TEXT NOT NULL DEFAULT 'en',
  consent_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'web',
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT 'self',
  is_self INTEGER NOT NULL DEFAULT 0,
  sex TEXT,
  dob TEXT,
  height_cm REAL,
  weight_kg REAL,
  activity TEXT NOT NULL DEFAULT 'sedentary',
  goal TEXT NOT NULL DEFAULT 'maintain',
  pregnant INTEGER NOT NULL DEFAULT 0,
  parental_consent_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS meals (
  id INTEGER PRIMARY KEY,
  member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  eaten_on TEXT NOT NULL,
  slot TEXT NOT NULL,
  source TEXT NOT NULL,
  raw_text TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS meals_member_day ON meals(member_id, eaten_on);
CREATE TABLE IF NOT EXISTS meal_items (
  id INTEGER PRIMARY KEY,
  meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
  food_id TEXT NOT NULL,
  name TEXT NOT NULL,
  quantity REAL NOT NULL,
  unit TEXT NOT NULL,
  grams REAL NOT NULL,
  kcal REAL NOT NULL, protein REAL NOT NULL, carbs REAL NOT NULL, fat REAL NOT NULL, fibre REAL NOT NULL,
  source TEXT NOT NULL,
  approx_of TEXT,
  note TEXT
);
CREATE TABLE IF NOT EXISTS health_records (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  record_id TEXT NOT NULL,
  type TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  source TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, record_id)
);
CREATE INDEX IF NOT EXISTS health_member_day ON health_records(member_id, type, start_time);
CREATE TABLE IF NOT EXISTS barcode_cache (
  code TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS coach_cache (
  member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  week_end TEXT NOT NULL,
  lang TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (member_id, week_end, lang)
);
"""


def path() -> Path:
    return Path(os.environ.get("TEJU_DB", DEFAULT_DB))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def get_conn():
    """FastAPI dependency: one connection per request, committed on success."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
