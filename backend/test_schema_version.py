import os
import sqlite3
import sys
import tempfile


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from schema_version import record_schema_version, schema_is_current


def test_schema_version_is_written_only_for_exact_component_version():
    with tempfile.TemporaryDirectory(prefix="door_schema_version_") as temp_dir:
        db_path = os.path.join(temp_dir, "schema.db")
        conn = sqlite3.connect(db_path)
        try:
            assert not schema_is_current(conn, "inventory", 1)
            record_schema_version(conn, "inventory", 1, "2026-09-19T00:00:00+08:00")
            conn.commit()
            assert schema_is_current(conn, "inventory", 1)
            assert not schema_is_current(conn, "inventory", 2)
            assert not schema_is_current(conn, "fulfillment", 1)
        finally:
            conn.close()


def test_failed_migration_does_not_advance_schema_version():
    with tempfile.TemporaryDirectory(prefix="door_schema_failure_") as temp_dir:
        db_path = os.path.join(temp_dir, "schema.db")
        conn = sqlite3.connect(db_path)
        try:
            assert not schema_is_current(conn, "fulfillment", 1)
            conn.rollback()
        finally:
            conn.close()

        reopened = sqlite3.connect(db_path)
        try:
            assert not schema_is_current(reopened, "fulfillment", 1)
        finally:
            reopened.close()
