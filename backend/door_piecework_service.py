"""Whole-door operation fees. Production completion and payment are separate."""

import json
from decimal import Decimal, InvalidOperation


def money_cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise ValueError("金额必须为非负数，且最多两位小数")
        cents = int(amount * 100)
        if cents > 9_000_000_000_000_000:
            raise ValueError("金额超出支持范围")
        return cents
    except (InvalidOperation, TypeError, OverflowError) as exc:
        raise ValueError("金额格式无效") from exc


def migrate_piecework(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(fulfillment_door_units)")}
    if "billing_mode" not in columns:
        conn.execute("ALTER TABLE fulfillment_door_units ADD COLUMN billing_mode TEXT NOT NULL DEFAULT 'legacy'")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(process_route_template_steps)")}
    if "applicable_groups_json" not in columns:
        from component_route_service import DEFAULT_GROUPS
        conn.execute("ALTER TABLE process_route_template_steps ADD COLUMN applicable_groups_json TEXT NOT NULL DEFAULT '[]'")
        for code, groups in DEFAULT_GROUPS.items():
            conn.execute("UPDATE process_route_template_steps SET applicable_groups_json=? WHERE step_code=?", (json.dumps(groups), code))
    for statement in (
        """CREATE TABLE IF NOT EXISTS door_operation_fees(
            id INTEGER PRIMARY KEY AUTOINCREMENT, door_unit_id INTEGER NOT NULL,
            technical_package_id INTEGER NOT NULL, billing_operation_code TEXT NOT NULL,
            name TEXT NOT NULL, template_snapshot_json TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity=1), unit TEXT NOT NULL DEFAULT '樘',
            total_cents INTEGER NOT NULL CHECK(total_cents>=0), status TEXT NOT NULL DEFAULT '加工中',
            revision INTEGER NOT NULL DEFAULT 1, completed_at TEXT, confirmed_at TEXT,
            confirmed_by TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
            UNIQUE(door_unit_id,billing_operation_code),
            FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id))""",
        """CREATE TABLE IF NOT EXISTS door_operation_fee_work(
            fee_id INTEGER NOT NULL, work_package_id INTEGER NOT NULL,
            PRIMARY KEY(fee_id,work_package_id),
            FOREIGN KEY(fee_id) REFERENCES door_operation_fees(id),
            FOREIGN KEY(work_package_id) REFERENCES fulfillment_work_packages(id))""",
        """CREATE TABLE IF NOT EXISTS door_operation_allocations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, fee_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),
            note TEXT NOT NULL DEFAULT '', UNIQUE(fee_id,employee_id),
            FOREIGN KEY(fee_id) REFERENCES door_operation_fees(id),
            FOREIGN KEY(employee_id) REFERENCES workforce_employees(id))""",
    ):
        conn.execute(statement)


class DoorPieceworkService:
    @staticmethod
    def publish(conn, door_id, package_id, now):
        door = conn.execute("SELECT billing_mode FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
        if not door or door["billing_mode"] != "whole_door":
            return
        grouped = {}
        works = conn.execute("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no,id", (package_id,)).fetchall()
        for work in works:
            snapshot = json.loads(work["route_snapshot_json"] or "{}")
            code = snapshot.get("billing_operation_code")
            if code:
                grouped.setdefault(code, []).append((work, snapshot))
        for code, members in grouped.items():
            snapshot = members[0][1]
            total = money_cents(snapshot["piece_rate"])
            if any(money_cents(item[1]["piece_rate"]) != total for item in members):
                raise ValueError("同一整门工序的计件快照不一致")
            existing = conn.execute("SELECT * FROM door_operation_fees WHERE door_unit_id=? AND billing_operation_code=?", (door_id, code)).fetchone()
            if existing and existing["status"] == "已确认":
                if existing["technical_package_id"] != package_id:
                    for work, work_snapshot in members:
                        work_snapshot["supplementary_work"] = True
                        conn.execute("UPDATE fulfillment_work_packages SET route_snapshot_json=? WHERE id=?", (json.dumps(work_snapshot, ensure_ascii=False), work["id"]))
                continue
            if existing and existing["technical_package_id"] == package_id and existing["status"] != "需核对":
                continue
            if existing:
                fee_id = existing["id"]
                conn.execute("DELETE FROM door_operation_allocations WHERE fee_id=?", (fee_id,))
                conn.execute("DELETE FROM door_operation_fee_work WHERE fee_id=?", (fee_id,))
                conn.execute("UPDATE door_operation_fees SET technical_package_id=?, name=?, template_snapshot_json=?, total_cents=?, status='加工中', revision=revision+1, completed_at=NULL, updated_at=? WHERE id=?", (package_id, snapshot["name"], json.dumps(snapshot, ensure_ascii=False), total, now, fee_id))
                conn.execute("INSERT INTO fulfillment_events(door_unit_id,entity_type,entity_id,action,detail,operator_uid,operator_name,created_at) VALUES (?,'piecework',?,'重建计件快照','技术版本变更，已清空未确认分配草稿','','',?)", (door_id, fee_id, now))
            else:
                fee_id = conn.execute("INSERT INTO door_operation_fees(door_unit_id,technical_package_id,billing_operation_code,name,template_snapshot_json,total_cents,updated_at) VALUES (?,?,?,?,?,?,?)", (door_id, package_id, code, snapshot["name"], json.dumps(snapshot, ensure_ascii=False), total, now)).lastrowid
            conn.executemany("INSERT INTO door_operation_fee_work(fee_id,work_package_id) VALUES (?,?)", [(fee_id, member[0]["id"]) for member in members])

    @staticmethod
    def readiness(conn, fee):
        context = conn.execute("""SELECT d.billing_mode,o.status AS order_status,p.id AS latest_id,p.status AS package_status
            FROM fulfillment_door_units d JOIN fulfillment_orders o ON o.id=d.order_id
            JOIN fulfillment_technical_packages p ON p.door_unit_id=d.id
            WHERE d.id=? ORDER BY p.version DESC LIMIT 1""", (fee["door_unit_id"],)).fetchone()
        if not context or context["billing_mode"] != "whole_door" or context["order_status"] in ("已取消", "已作废"):
            return "需核对", None
        if context["latest_id"] != fee["technical_package_id"] or context["package_status"] != "已确认" or fee["status"] == "需核对":
            return "需核对", None
        works = conn.execute("SELECT w.status,w.completed_at FROM door_operation_fee_work m LEFT JOIN fulfillment_work_packages w ON w.id=m.work_package_id WHERE m.fee_id=?", (fee["id"],)).fetchall()
        if not works or any(w["status"] in (None, "已取消") for w in works):
            return "需核对", None
        if any(w["status"] != "已完成" or not w["completed_at"] for w in works):
            return "加工中", None
        return ("待分配" if fee["total_cents"] else "未设置计件单价"), max(w["completed_at"] for w in works)

    @classmethod
    def list(cls, conn, door_id):
        rows = conn.execute("SELECT * FROM door_operation_fees WHERE door_unit_id=? ORDER BY id", (door_id,)).fetchall()
        return [cls.payload(conn, row) for row in rows]

    @classmethod
    def payload(cls, conn, row):
        result = dict(row)
        result["template_snapshot"] = json.loads(result.pop("template_snapshot_json"))
        result["allocations"] = [dict(a) for a in conn.execute("SELECT a.*,e.employee_no,e.name AS employee_name FROM door_operation_allocations a JOIN workforce_employees e ON e.id=a.employee_id WHERE fee_id=? ORDER BY employee_id", (row["id"],))]
        result["allocated_cents"] = sum(a["amount_cents"] for a in result["allocations"])
        result["remaining_cents"] = row["total_cents"] - result["allocated_cents"]
        if row["status"] != "已确认":
            result["status"], result["completed_at"] = cls.readiness(conn, row)
        return result

    @classmethod
    def save_allocations(cls, conn, fee_id, revision, allocations, confirm, now, user_uid=""):
        fee = conn.execute("SELECT * FROM door_operation_fees WHERE id=?", (fee_id,)).fetchone()
        if not fee:
            raise LookupError("整门工序计件不存在")
        values = [(item.employee_id, money_cents(item.amount), item.note) for item in allocations]
        if len({v[0] for v in values}) != len(values):
            raise ValueError("同一工序的分配人员不能重复")
        if sum(v[1] for v in values) > fee["total_cents"]:
            raise ValueError("分配合计不能超过整门工序总额")
        if fee["status"] == "已确认":
            existing = [(a["employee_id"], a["amount_cents"], a["note"]) for a in conn.execute("SELECT * FROM door_operation_allocations WHERE fee_id=?", (fee_id,))]
            if confirm and sorted(existing) == sorted(values):
                return cls.payload(conn, fee)
            raise RuntimeError("已确认分配不能直接修改或删除")
        if revision != fee["revision"]:
            raise RuntimeError("计件记录已更新，请刷新后重新分配")
        status, completed_at = cls.readiness(conn, fee)
        if status != "待分配":
            raise RuntimeError(f"工序当前为{status}，不能分配计件")
        if confirm and not values:
            raise ValueError("请选择至少一名分配人员")
        for employee_id, _, _ in values:
            if not conn.execute("SELECT id FROM workforce_employees WHERE id=? AND is_active=1", (employee_id,)).fetchone():
                raise ValueError("分配人员不存在或已停用")
        if confirm:
            period = conn.execute("SELECT status FROM payroll_periods WHERE month=?", (completed_at[:7],)).fetchone()
            if period and period["status"] in ("已审批", "已锁定"):
                raise RuntimeError("工序完成月份的工资已审批或锁定，不能确认分配")
        conn.execute("DELETE FROM door_operation_allocations WHERE fee_id=?", (fee_id,))
        conn.executemany("INSERT INTO door_operation_allocations(fee_id,employee_id,amount_cents,note) VALUES (?,?,?,?)", [(fee_id, *v) for v in values])
        conn.execute("UPDATE door_operation_fees SET revision=revision+1,status=?,completed_at=?,confirmed_at=?,confirmed_by=?,updated_at=? WHERE id=?", ("已确认" if confirm else "加工中", completed_at if confirm else None, now if confirm else None, user_uid if confirm else "", now, fee_id))
        return cls.payload(conn, conn.execute("SELECT * FROM door_operation_fees WHERE id=?", (fee_id,)).fetchone())
