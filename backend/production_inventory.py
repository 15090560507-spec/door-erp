"""Replay semi-finished movements without rewriting historical source positions."""

from __future__ import annotations

import sqlite3
from typing import Any


EPSILON = 1e-6


def semi_finished_balances(
    conn: sqlite3.Connection, *, door_id: int | None = None, package_id: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["m.movement_type IN ('半成品入库','拼装领用')", "m.component_id IS NOT NULL"]
    params = []
    for column, value in (("door_unit_id", door_id), ("technical_package_id", package_id)):
        if value is not None:
            clauses.append(f"m.{column}=?")
            params.append(value)
    movements = conn.execute(
        f"""SELECT m.*, c.specification, d.production_no, d.product_name AS door_type,
                   d.status, o.customer, o.project
            FROM fulfillment_inventory_movements m
            JOIN fulfillment_door_units d ON d.id=m.door_unit_id
            JOIN fulfillment_orders o ON o.id=d.order_id
            LEFT JOIN fulfillment_components c ON c.id=m.component_id
            WHERE {' AND '.join(clauses)} ORDER BY m.created_at, m.id""", params,
    ).fetchall()
    positions: dict[tuple, dict[str, Any]] = {}
    lots: dict[tuple, list[dict[str, Any]]] = {}
    inferred_subjects = set()
    anomalous_subjects = set()

    def position(movement, warehouse, location):
        subject = (movement["door_unit_id"], movement["technical_package_id"], movement["component_id"])
        key = (*subject, warehouse, location)
        if key not in positions:
            positions[key] = {
                "warehouse_type": "半成品", "warehouse": warehouse, "location": location,
                "door_unit_id": subject[0], "technical_package_id": subject[1], "component_id": subject[2],
                "item_name": movement["item_name"], "specification": movement["specification"] or "",
                "production_no": movement["production_no"], "door_type": movement["door_type"],
                "width": 0, "height": 0, "status": movement["status"],
                "customer": movement["customer"], "project": movement["project"],
                "unit": movement["unit"], "quantity": 0.0, "inbound_quantity": 0.0,
                "issued_quantity": 0.0, "updated_at": movement["created_at"],
            }
        row = positions[key]
        row["updated_at"] = max(row["updated_at"], movement["created_at"])
        return subject, key, row

    for movement in movements:
        warehouse, location = movement["warehouse"] or "", movement["location"] or ""
        subject, key, row = position(movement, warehouse, location)
        quantity = float(movement["quantity"] or 0)
        subject_lots = lots.setdefault(subject, [])
        if movement["movement_type"] == "半成品入库":
            # A later receipt first repays an explicit position deficit.
            available = max(0.0, quantity + min(0.0, row["quantity"]))
            row["quantity"] += quantity
            row["inbound_quantity"] += quantity
            subject_lots.append({"key": key, "quantity": available})
            continue

        if location:
            row["quantity"] -= quantity
            row["issued_quantity"] += quantity
            candidates = [lot for lot in subject_lots if lot["key"] == key]
        else:
            inferred_subjects.add(subject)
            candidates = [lot for lot in subject_lots if lot["key"][-2] == warehouse]
            if warehouse == "半成品仓":
                candidates += [lot for lot in subject_lots if lot["key"][-2] != warehouse]
        remaining = quantity
        for lot in candidates:
            take = min(remaining, lot["quantity"])
            if take <= EPSILON:
                continue
            lot["quantity"] -= take
            remaining -= take
            if not location:
                source = positions[lot["key"]]
                source["quantity"] -= take
                source["issued_quantity"] += take
                source["updated_at"] = max(source["updated_at"], movement["created_at"])
            if remaining <= EPSILON:
                break
        if remaining > EPSILON:
            anomalous_subjects.add(subject)
            if not location:
                row["quantity"] -= remaining
                row["issued_quantity"] += remaining

    for key, row in positions.items():
        row["available_quantity"] = max(0.0, row["quantity"])
        row["source_inferred"] = key[:3] in inferred_subjects
        row["stock_anomaly"] = key[:3] in anomalous_subjects or row["quantity"] < -EPSILON
    available_order = {}
    for subject_lots in lots.values():
        for index, lot in enumerate(subject_lots):
            if lot["quantity"] > EPSILON:
                available_order.setdefault(lot["key"], index)
    return [row for key, row in sorted(positions.items(), key=lambda item: available_order.get(item[0], float("inf")))]
