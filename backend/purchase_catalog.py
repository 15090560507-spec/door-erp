"""Catalog capture limited to the current purchase transaction, not general editing."""
import math
import sqlite3
from uuid import uuid4


def resolve_supplier(conn: sqlite3.Connection, payload: dict, now: str) -> sqlite3.Row:
    name = str(payload.get("supplier") or "").strip()
    supplier_id = payload.get("supplier_id")
    if supplier_id:
        row = conn.execute("SELECT * FROM inventory_suppliers WHERE id=?", (supplier_id,)).fetchone()
        if not row or not row["is_active"]:
            raise LookupError("供应商不存在或已停用")
        if row["name"] != name:
            raise ValueError("供应商名称与所选资料不一致，请重新选择")
        return row
    rows = conn.execute("SELECT * FROM inventory_suppliers WHERE trim(name)=?", (name,)).fetchall()
    if rows:
        if len(rows) != 1 or not rows[0]["is_active"]:
            raise ValueError("存在重名或已停用供应商，请从资料中明确选择有效供应商")
        return rows[0]
    cursor = conn.execute(
        "INSERT INTO inventory_suppliers(code,name,remark,created_at,updated_at) VALUES (?,?,?,?,?)",
        (f"CGS-{uuid4().hex[:12].upper()}", name, "采购建档", now, now),
    )
    return conn.execute("SELECT * FROM inventory_suppliers WHERE id=?", (cursor.lastrowid,)).fetchone()


def resolve_material(conn: sqlite3.Connection, item: dict, now: str) -> sqlite3.Row:
    material_id = item.get("material_id")
    if material_id:
        row = conn.execute("SELECT * FROM inventory_materials WHERE id=? AND is_active=1", (material_id,)).fetchone()
        if not row or not row["can_purchase"]:
            raise LookupError("采购物料不存在、已停用或不可采购")
        return row
    name = str(item.get("material_name") or "").strip()
    specification = str(item.get("specification") or "").strip()
    unit = str(item.get("unit") or "").strip()
    if not name or not unit:
        raise ValueError("新物料必须填写名称和单位")
    if item.get("allocations"):
        raise ValueError("关联需求必须选择已有物料")
    rows = conn.execute(
        "SELECT * FROM inventory_materials WHERE trim(name)=? AND trim(specification)=? AND trim(unit)=?",
        (name, specification, unit),
    ).fetchall()
    if rows:
        if len(rows) != 1 or not rows[0]["is_active"] or not rows[0]["can_purchase"]:
            raise ValueError("存在同名同规格的停用、不可采购或重复物料，请从资料中明确选择")
        return rows[0]
    cursor = conn.execute(
        """INSERT INTO inventory_materials(code,name,specification,unit,material_type,
               purchase_unit,remark,created_at,updated_at) VALUES (?,?,?,?,'原材料',?,?,?,?)""",
        (f"CGW-{uuid4().hex[:12].upper()}", name, specification, unit, unit, "采购建档", now, now),
    )
    return conn.execute("SELECT * FROM inventory_materials WHERE id=?", (cursor.lastrowid,)).fetchone()


def ensure_supply(conn: sqlite3.Connection, supplier: sqlite3.Row, material: sqlite3.Row, now: str) -> None:
    existing = conn.execute("SELECT * FROM inventory_supplier_items WHERE supplier_id=? AND material_id=?", (supplier["id"], material["id"])).fetchone()
    if existing:
        if not existing["is_active"]:
            raise ValueError("该供应商的供货关系已停用，请先在基础资料中处理")
        return
    conn.execute(
        """INSERT INTO inventory_supplier_items(supplier_id,material_id,supplier_item_name,
               purchase_specification,purchase_unit,tax_rate,remark,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (supplier["id"], material["id"], material["name"], material["specification"], material["unit"],
         supplier["default_tax_rate"], "采购建档", now, now),
    )


def publish_prices(conn: sqlite3.Connection, order: sqlite3.Row, actor: str, now: str) -> None:
    # Legacy text-only orders are intentionally not relinked by guessed supplier names.
    if not order["supplier_id"]:
        return
    supplier = conn.execute("SELECT * FROM inventory_suppliers WHERE id=? AND is_active=1", (order["supplier_id"],)).fetchone()
    if not supplier:
        raise ValueError("供应商已停用，请先核对基础资料")
    # Different negotiated prices on separate lines remain intact; the catalog gets
    # the quantity-weighted unit price for this confirmed purchase.
    items = conn.execute(
        """SELECT material_id, SUM(ordered_quantity*unit_price)/SUM(ordered_quantity) AS unit_price
           FROM purchase_order_items WHERE purchase_order_id=? GROUP BY material_id""",
        (order["id"],),
    ).fetchall()
    for item in items:
        material = conn.execute("SELECT * FROM inventory_materials WHERE id=? AND is_active=1 AND can_purchase=1", (item["material_id"],)).fetchone()
        if not material:
            raise ValueError("采购物料已停用或不可采购")
        ensure_supply(conn, supplier, material, now)
        relation = conn.execute("SELECT * FROM inventory_supplier_items WHERE supplier_id=? AND material_id=?", (supplier["id"], item["material_id"])).fetchone()
        conversion = float(relation["conversion_rate"])
        if not math.isfinite(conversion) or conversion <= 0:
            raise ValueError("供应商采购单位换算无效，请先核对供货资料")
        price = round(float(item["unit_price"]) * conversion, 6)
        if not math.isfinite(price):
            raise ValueError("采购单位换算后的价格超出有效范围")
        history = conn.execute("SELECT 1 FROM inventory_supplier_item_prices WHERE supplier_item_id=? LIMIT 1", (relation["id"],)).fetchone()
        if not history or abs(price - float(relation["tax_inclusive_price"])) > 1e-9:
            conn.execute("UPDATE inventory_supplier_items SET tax_inclusive_price=?, updated_at=? WHERE id=?", (price, now, relation["id"]))
            conn.execute(
                """INSERT INTO inventory_supplier_item_prices(supplier_item_id,tax_inclusive_price,
                       tax_rate,effective_date,operator_uid,created_at) VALUES (?,?,?,?,?,?)""",
                (relation["id"], price, relation["tax_rate"], now[:10], actor, now),
            )
