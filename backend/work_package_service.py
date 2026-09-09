"""Dependency-aware workshop route generation and readiness calculation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence


EPSILON = 1e-9


@dataclass(frozen=True)
class RouteNode:
    code: str
    name: str
    category: str
    weight: float
    predecessors: Sequence[str] = field(default_factory=tuple)
    material_operations: Sequence[str] = field(default_factory=tuple)
    inspection_required: bool = False


PANEL_OPERATIONS = ("PANEL", "SKELETON")
FITTING_OPERATIONS = (
    "TRIM", "GLASS", "HINGE", "LOCK_BODY", "FINGERPRINT_LOCK",
    "FRONT_HANDLE", "BACK_HANDLE", "ORNAMENT", "CONSUMABLE",
)
FRAME_OPERATIONS = {"FRAME_ASSEMBLY", "FRAME_PART"}


class WorkPackageService:
    """Build the current route and derive readiness from actual business events."""

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone())

    @staticmethod
    def _route(operation_codes: set[str]) -> List[RouteNode]:
        has_panel = bool(operation_codes.intersection(PANEL_OPERATIONS))
        has_fittings = bool(operation_codes.intersection(FITTING_OPERATIONS))
        has_subcontract = "SUBCONTRACT" in operation_codes

        nodes = [RouteNode("TECH_PREP", "技术准备", "技术", 5)]
        assembly_predecessors: List[str] = []

        if has_panel:
            nodes.extend([
                RouteNode("PANEL_PREP", "门板与骨架备料", "备料", 10, ("TECH_PREP",), PANEL_OPERATIONS),
                RouteNode("PANEL_CUT", "板材下料", "下料", 12, ("PANEL_PREP",)),
                RouteNode("BENDING", "折弯成型", "折弯", 10, ("PANEL_CUT",)),
                RouteNode("BODY", "门体焊接与制作", "门体", 20, ("BENDING",)),
                RouteNode("SURFACE", "表面处理", "表面", 14, ("BODY",)),
            ])
            assembly_predecessors.append("SURFACE")

        if has_fittings:
            nodes.append(RouteNode(
                "FITTINGS_PREP", "玻璃五金与门套配套", "配套", 10,
                ("TECH_PREP",), FITTING_OPERATIONS,
            ))
            assembly_predecessors.append("FITTINGS_PREP")

        if has_subcontract:
            nodes.append(RouteNode("SUBCONTRACT", "外协加工", "外协", 15, ("TECH_PREP",)))
            assembly_predecessors.append("SUBCONTRACT")

        if not assembly_predecessors:
            assembly_predecessors.append("TECH_PREP")
        nodes.extend([
            RouteNode("ASSEMBLY", "总装配", "装配", 15, tuple(assembly_predecessors)),
            RouteNode("PACKAGING", "成品包装", "包装", 5, ("ASSEMBLY",), ("PACKAGING",)),
            RouteNode("QC_HANDOFF", "成品质检交接", "质检", 5, ("PACKAGING",), inspection_required=True),
        ])
        return nodes

    def generate_for_package(
        self,
        conn: sqlite3.Connection,
        *,
        door_id: int,
        package_id: int,
        now: str,
    ) -> int:
        """Replace draft/manual route rows with an idempotent BOM-derived route."""
        existing = conn.execute(
            "SELECT COUNT(*) AS total FROM fulfillment_work_packages WHERE technical_package_id=? AND operation_code!=''",
            (package_id,),
        ).fetchone()
        if existing and int(existing["total"] or 0) > 0:
            self.recompute(conn, door_id=door_id, now=now)
            return int(existing["total"])

        work_ids = [int(row["id"]) for row in conn.execute(
            "SELECT id FROM fulfillment_work_packages WHERE technical_package_id=?", (package_id,)
        ).fetchall()]
        if work_ids:
            placeholders = ",".join("?" for _ in work_ids)
            conn.execute(
                f"DELETE FROM fulfillment_work_package_dependencies WHERE predecessor_id IN ({placeholders}) OR successor_id IN ({placeholders})",
                (*work_ids, *work_ids),
            )
        conn.execute("DELETE FROM fulfillment_work_packages WHERE technical_package_id=?", (package_id,))

        operation_codes = {
            str(row["operation_code"] or "")
            for row in conn.execute(
                "SELECT operation_code FROM fulfillment_components WHERE technical_package_id=?",
                (package_id,),
            ).fetchall()
        }
        # Frame BOM remains traceable, but frame cutting is deliberately deferred.
        operation_codes.difference_update(FRAME_OPERATIONS)
        route = self._route(operation_codes)
        ids_by_code: Dict[str, int] = {}
        for sequence, node in enumerate(route, start=1):
            cursor = conn.execute(
                """INSERT INTO fulfillment_work_packages(
                       technical_package_id, door_unit_id, name, category, route,
                       acquisition_method, opening_condition, blocking_node,
                       quantity, unit, inspection_required, status, sequence_no,
                       operation_code, weight, readiness_status, material_ready,
                       updated_at
                   ) VALUES (?, ?, ?, ?, ?, '内部加工', ?, ?, 1, '樘', ?,
                             '待排单', ?, ?, ?, '待前序', 0, ?)""",
                (
                    package_id, door_id, node.name, node.category, node.name,
                    "BOM已发布", "、".join(node.predecessors),
                    int(node.inspection_required), sequence, node.code, node.weight, now,
                ),
            )
            ids_by_code[node.code] = int(cursor.lastrowid)
        for node in route:
            for predecessor in node.predecessors:
                conn.execute(
                    """INSERT OR IGNORE INTO fulfillment_work_package_dependencies(
                           predecessor_id, successor_id, created_at
                       ) VALUES (?, ?, ?)""",
                    (ids_by_code[predecessor], ids_by_code[node.code], now),
                )
        self.recompute(conn, door_id=door_id, now=now)
        return len(route)

    @staticmethod
    def _material_state(
        conn: sqlite3.Connection,
        package_id: int,
        operation_codes: Iterable[str],
    ) -> tuple[bool, str]:
        codes = tuple(operation_codes)
        if not codes:
            return True, ""
        placeholders = ",".join("?" for _ in codes)
        rows = conn.execute(
            f"""SELECT i.material_name, i.required_quantity, i.reserved_quantity,
                       i.shortage_quantity, i.issued_quantity, i.returned_quantity, i.unit
                FROM material_requirement_items i
                JOIN fulfillment_components c ON c.id=i.component_id
                WHERE i.technical_package_id=? AND c.operation_code IN ({placeholders})
                ORDER BY i.sequence_no, i.id""",
            (package_id, *codes),
        ).fetchall()
        if not rows:
            return True, ""
        pending = []
        for row in rows:
            required = float(row["required_quantity"] or 0)
            issued = max(0.0, float(row["issued_quantity"] or 0) - float(row["returned_quantity"] or 0))
            if required - issued <= EPSILON:
                continue
            if float(row["shortage_quantity"] or 0) > EPSILON:
                state = "缺料"
            elif float(row["reserved_quantity"] or 0) > EPSILON:
                state = "待仓库发料"
            else:
                state = "待物料"
            pending.append(f"{row['material_name']} {issued:g}/{required:g}{row['unit']}（{state}）")
        return (not pending), "；".join(pending[:3])

    def recompute(self, conn: sqlite3.Connection, *, door_id: int, now: str) -> None:
        if not self._table_exists(conn, "fulfillment_work_package_dependencies"):
            return
        package = conn.execute(
            "SELECT id, status FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
            (door_id,),
        ).fetchone()
        if not package:
            return
        package_id = int(package["id"])
        rows = conn.execute(
            "SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no, id",
            (package_id,),
        ).fetchall()
        statuses = {int(row["id"]): str(row["status"]) for row in rows}
        names = {int(row["id"]): str(row["name"]) for row in rows}
        dependencies: Dict[int, List[int]] = {}
        for dependency in conn.execute(
            """SELECT d.predecessor_id, d.successor_id
               FROM fulfillment_work_package_dependencies d
               JOIN fulfillment_work_packages w ON w.id=d.successor_id
               WHERE w.technical_package_id=?""",
            (package_id,),
        ).fetchall():
            dependencies.setdefault(int(dependency["successor_id"]), []).append(int(dependency["predecessor_id"]))

        material_gates = {
            "PANEL_PREP": PANEL_OPERATIONS,
            "FITTINGS_PREP": FITTING_OPERATIONS,
            "PACKAGING": ("PACKAGING",),
        }
        for row in rows:
            work_id = int(row["id"])
            status = str(row["status"])
            ready_at = row["ready_at"]
            if status == "已完成":
                readiness, material_ready, reason = "已完成", 1, ""
            elif status == "已取消":
                readiness, material_ready, reason = "已跳过", 1, str(row["skip_reason"] or row["remark"] or "")
            elif str(package["status"]) != "已确认":
                readiness, material_ready, reason = "待发布", 0, "BOM尚未发布"
            else:
                predecessors = dependencies.get(work_id, [])
                blocked = [names[item] for item in predecessors if statuses.get(item) not in {"已完成", "已取消"}]
                material_ready_bool, material_reason = self._material_state(
                    conn, package_id, material_gates.get(str(row["operation_code"] or ""), ()),
                )
                material_ready = int(material_ready_bool)
                if blocked:
                    readiness, reason = "待前序", f"等待：{'、'.join(blocked)}"
                elif not material_ready_bool:
                    readiness, reason = "待物料", material_reason
                elif status == "进行中":
                    readiness, reason = "进行中", ""
                elif status == "待质检":
                    readiness, reason = "待确认", ""
                elif status in {"异常", "返工", "暂停"}:
                    readiness, reason = status, str(row["remark"] or "")
                else:
                    readiness, reason = "可执行", ""
                    ready_at = ready_at or now
            conn.execute(
                """UPDATE fulfillment_work_packages
                   SET readiness_status=?, material_ready=?, blocked_reason=?, ready_at=?, updated_at=?
                   WHERE id=?""",
                (readiness, material_ready, reason, ready_at, now, work_id),
            )
        self.refresh_progress(conn, door_id=door_id, now=now)

    def ensure_startable(self, conn: sqlite3.Connection, *, work_id: int, now: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM fulfillment_work_packages WHERE id=?", (work_id,)).fetchone()
        if not row:
            raise LookupError("工作包不存在")
        self.recompute(conn, door_id=int(row["door_unit_id"]), now=now)
        current = conn.execute("SELECT * FROM fulfillment_work_packages WHERE id=?", (work_id,)).fetchone()
        if current and str(current["readiness_status"]) not in {"可执行", "返工", "暂停", "异常"}:
            reason = str(current["blocked_reason"] or current["readiness_status"])
            raise RuntimeError(f"工作包尚不可执行：{reason}")
        return current

    def refresh_progress(self, conn: sqlite3.Connection, *, door_id: int, now: str) -> None:
        package = conn.execute(
            "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
            (door_id,),
        ).fetchone()
        rows = conn.execute(
            "SELECT status, operation_code, weight FROM fulfillment_work_packages WHERE technical_package_id=?",
            (package["id"] if package else -1,),
        ).fetchall()
        fractions = {
            "草稿": 0, "待排单": 0, "已排单": 0.05, "进行中": 0.5,
            "待质检": 0.9, "已完成": 1, "暂停": 0.25, "异常": 0.25,
            "返工": 0.4, "已取消": 1,
        }
        total_weight = sum(max(0.0, float(row["weight"] or 0)) for row in rows)
        achieved = sum(
            max(0.0, float(row["weight"] or 0)) * fractions.get(str(row["status"]), 0)
            for row in rows
        )
        progress = int(round(achieved * 100 / total_weight)) if total_weight > EPSILON else 0
        all_done = bool(rows) and all(str(row["status"]) in {"已完成", "已取消"} for row in rows)
        assembly_started = any(
            str(row["operation_code"]) == "ASSEMBLY" and str(row["status"]) in {"进行中", "待质检", "已完成"}
            for row in rows
        )
        conn.execute(
            """UPDATE fulfillment_door_units
               SET progress=?,
                   status=CASE
                       WHEN ? AND status IN ('技术准备中','备料与加工中','可局部装配','总装中') THEN '待成品质检'
                       WHEN ? AND status IN ('技术准备中','备料与加工中','可局部装配') THEN '总装中'
                       WHEN ? AND status='技术准备中' THEN '备料与加工中'
                       ELSE status END,
                   updated_at=? WHERE id=?""",
            (progress, int(all_done), int(assembly_started), int(progress > 0), now, door_id),
        )

    def recompute_for_material(self, conn: sqlite3.Connection, *, material_id: int, now: str) -> None:
        if not self._table_exists(conn, "fulfillment_work_packages"):
            return
        door_ids = conn.execute(
            """SELECT DISTINCT i.door_unit_id
               FROM material_requirement_items i
               JOIN material_requirements r ON r.id=i.requirement_id
               WHERE i.material_id=? AND r.status!='已冻结'""",
            (material_id,),
        ).fetchall()
        for row in door_ids:
            self.recompute(conn, door_id=int(row["door_unit_id"]), now=now)
