"""Lightweight schema-version guards for SQLite repositories."""

from __future__ import annotations

import sqlite3


def schema_is_current(conn: sqlite3.Connection, component: str, version: int) -> bool:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS app_schema_versions (
               component TEXT PRIMARY KEY,
               version INTEGER NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    row = conn.execute(
        "SELECT version FROM app_schema_versions WHERE component=?",
        (component,),
    ).fetchone()
    return bool(row and int(row[0]) == version)


def record_schema_version(
    conn: sqlite3.Connection,
    component: str,
    version: int,
    updated_at: str,
) -> None:
    conn.execute(
        """INSERT INTO app_schema_versions(component, version, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(component) DO UPDATE SET
             version=excluded.version,
             updated_at=excluded.updated_at""",
        (component, version, updated_at),
    )
