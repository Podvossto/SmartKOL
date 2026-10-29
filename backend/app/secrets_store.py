"""Encrypted key/value storage (SQLite + Fernet) for user-supplied credentials."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


def data_dir() -> Path:
    path = Path(os.environ.get("SMARTKOL_DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fernet() -> Fernet:
    env_key = os.environ.get("SMARTKOL_SECRET_KEY")
    if env_key:
        return Fernet(env_key.encode())
    key_file = data_dir() / "secret.key"
    if not key_file.exists():
        key_file.write_bytes(Fernet.generate_key())
    return Fernet(key_file.read_bytes().strip())


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "smartkol.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS secrets ("
        "name TEXT PRIMARY KEY, value BLOB NOT NULL, updated_at TEXT NOT NULL)"
    )
    return conn


def put(name: str, value: dict) -> None:
    token = _fernet().encrypt(json.dumps(value).encode())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO secrets (name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (name, token, datetime.now(timezone.utc).isoformat()),
        )


def get(name: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM secrets WHERE name = ?", (name,)).fetchone()
    return json.loads(_fernet().decrypt(row[0])) if row else None


def delete(name: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
