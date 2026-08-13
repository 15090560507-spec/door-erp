"""SQLite repository for factory-wide inventory data."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence
from zoneinfo import ZoneInfo

from config import FULFILLMENT_DB_FILE


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_WAREHOUSES = (
    ("RAW", "原材料仓", "原材料"),
    ("ACCESSORY", "配件仓", "配件"),
    ("SEMI", "半成品仓", "半成品"),
    ("SUBCONTRACT", "外协在途仓", "外协在途"),
    ("FINISHED", "成品仓", "成品"),
)


def inventory_now() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")


class InventoryDatabase:
    def __init__(self, db_path: str = FULFILLMENT_DB_FILE):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @contextmanager
    def transaction(self, existing: Optional[sqlite3.Connection] = None) -> Iterator[sqlite3.Connection]:
        if existing is not None:
            yield existing
            return
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        now = inventory_now()
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS inventory_warehouses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    warehouse_type TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inventory_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    warehouse_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(warehouse_id, code),
                    FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses(id)
                );

                CREATE TABLE IF NOT EXISTS inventory_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    specification TEXT NOT NULL DEFAULT '',
                    unit TEXT NOT NULL,
                    material_type TEXT NOT NULL,
                    default_warehouse_id INTEGER,
                    default_location_id INTEGER,
                    default_supplier TEXT NOT NULL DEFAULT '',
                    minimum_stock REAL NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(default_warehouse_id) REFERENCES inventory_warehouses(id),
                    FOREIGN KEY(default_location_id) REFERENCES inventory_locations(id)
                );

                CREATE TABLE IF NOT EXISTS inventory_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_no TEXT NOT NULL UNIQUE,
                    document_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '草稿',
                    remark TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    confirmed_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inventory_document_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    material_id INTEGER NOT NULL,
                    warehouse_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT NOT NULL,
                    remark TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(document_id) REFERENCES inventory_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY(material_id) REFERENCES inventory_materials(id),
                    FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses(id),
                    FOREIGN KEY(location_id) REFERENCES inventory_locations(id)
                );

                CREATE TABLE IF NOT EXISTS inventory_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    warehouse_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity <> 0),
                    unit TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_line TEXT NOT NULL DEFAULT '',
                    order_id INTEGER,
                    door_unit_id INTEGER,
                    production_no TEXT NOT NULL DEFAULT '',
                    operator_uid TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(source_type, source_id, source_line),
                    FOREIGN KEY(material_id) REFERENCES inventory_materials(id),
                    FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses(id),
                    FOREIGN KEY(location_id) REFERENCES inventory_locations(id)
                );

                CREATE TABLE IF NOT EXISTS inventory_balances (
                    material_id INTEGER NOT NULL,
                    warehouse_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    on_hand REAL NOT NULL DEFAULT 0,
                    reserved REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(material_id, warehouse_id, location_id),
                    FOREIGN KEY(material_id) REFERENCES inventory_materials(id),
                    FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses(id),
                    FOREIGN KEY(location_id) REFERENCES inventory_locations(id)
                );

                CREATE TABLE IF NOT EXISTS inventory_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_table TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    migrated_at TEXT NOT NULL,
                    remark TEXT NOT NULL DEFAULT '',
                    UNIQUE(source_table, source_id)
                );

                CREATE INDEX IF NOT EXISTS ix_inventory_material_search
                    ON inventory_materials(name, category, specification, is_active);
                CREATE INDEX IF NOT EXISTS ix_inventory_transaction_material
                    ON inventory_transactions(material_id, warehouse_id, location_id, created_at);
                CREATE INDEX IF NOT EXISTS ix_inventory_transaction_production
                    ON inventory_transactions(production_no, door_unit_id, created_at);

                CREATE TRIGGER IF NOT EXISTS inventory_transactions_no_update
                BEFORE UPDATE ON inventory_transactions
                BEGIN
                    SELECT RAISE(ABORT, '已确认库存流水不能修改');
                END;

                CREATE TRIGGER IF NOT EXISTS inventory_transactions_no_delete
                BEFORE DELETE ON inventory_transactions
                BEGIN
                    SELECT RAISE(ABORT, '已确认库存流水不能删除');
                END;
                """
            )
            conn.executemany(
                """INSERT INTO inventory_warehouses(
                       code, name, warehouse_type, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(code) DO NOTHING""",
                [(code, name, warehouse_type, now, now) for code, name, warehouse_type in DEFAULT_WAREHOUSES],
            )

    @staticmethod
    def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        return dict(row) if row else None

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        conn = self.connect()
        try:
            return self._row(conn.execute(sql, params).fetchone())
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        conn = self.connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def list_warehouses(self) -> List[Dict[str, Any]]:
        return self.fetch_all("SELECT * FROM inventory_warehouses ORDER BY id")
