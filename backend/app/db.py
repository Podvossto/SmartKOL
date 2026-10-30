"""SQLite connection + schema shared by credentials, analyses and the Apify result cache."""
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS secrets (
    name TEXT PRIMARY KEY, value BLOB NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analysis_logos (
    analysis_id TEXT PRIMARY KEY, content_type TEXT NOT NULL, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS analysis_media (
    analysis_id TEXT NOT NULL, key TEXT NOT NULL, content_type TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY (analysis_id, key));
CREATE TABLE IF NOT EXISTS apify_cache (
    key TEXT PRIMARY KEY, items TEXT NOT NULL, usd REAL NOT NULL, created_at TEXT NOT NULL);
"""


def data_dir() -> Path:
    path = Path(os.environ.get("SMARTKOL_DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "smartkol.db", timeout=30)
    conn.executescript(SCHEMA)
    return conn
