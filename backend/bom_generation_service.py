"""Version-aware automatic BOM generation over fulfillment technical packages."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from bom_rules import CURRENT_BOM_RULE_VERSION, BomRuleItem, BomRuleWarning, build_baseline_bom
from fulfillment_database import fulfillment_now, json_dumps, json_loads


def _normalized(value: Any) -> str:
    return re.sub(r"[\s\-_./]+", "", str(value or "")).lower()


class BomGenerationService:
    def __init__(self, database: Any):
        self.db = database

    @staticmethod
    def _match_material(connection: Any, item: BomRuleItem) -> Tuple[Optional[int], str, Optional[BomRuleWarning]]:
        if item.data_status != "ready":
            return None, "缺少资料", None
        if not item.requires_material:
            return None, "无需物料", None

        if item.material_code:
            rows = connection.execute(
                "SELECT * FROM inventory_materials WHERE lower(code)=lower(?) AND is_active=1",
                (item.material_code,),
            ).fetchall()
            if len(rows) == 1:
                return int(rows[0]["id"]), "已匹配", None
            warning = BomRuleWarning(
                field_path=f"material_code.{item.operation_code.lower()}",
                code="material_code_not_found" if not rows else "material_code_ambiguous",
                message=f"物料编码“{item.material_code}”未找到唯一有效物料",
            )
            return None, "待匹配" if not rows else "匹配冲突", warning

        link = connection.execute(
            """SELECT m.* FROM material_component_links l
               JOIN inventory_materials m ON m.id=l.material_id
               WHERE l.component_name=? AND l.component_category=?
                 AND l.component_specification=? AND m.is_active=1""",
            (item.name, item.category, item.specification),
        ).fetchall()
        if len(link) == 1:
            return int(link[0]["id"]), "已匹配", None

        materials = connection.execute("SELECT * FROM inventory_materials WHERE is_active=1").fetchall()
        name = _normalized(item.name)
        specification = _normalized(item.specification)
        exact = [
            row for row in materials
            if _normalized(row["name"]) == name
            and (not specification or _normalized(row["specification"]) == specification)
        ]
        if len(exact) == 1:
            return int(exact[0]["id"]), "已匹配", None
        if len(exact) > 1:
            return None, "匹配冲突", BomRuleWarning(
                field_path=f"material.{item.operation_code.lower()}",
                code="material_match_ambiguous",
                message=f"“{item.name} / {item.specification}”匹配到多个物料，请人工选择",
            )
        return None, "待匹配", BomRuleWarning(
            field_path=f"material.{item.operation_code.lower()}",
            code="material_not_matched",
            message=f"“{item.name} / {item.specification}”尚未关联物料档案",
        )

    def generate(
        self,
        door_unit_id: int,
        user: Dict[str, Any],
        rule_version: str = CURRENT_BOM_RULE_VERSION,
    ) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.db.transaction() as connection:
            door = connection.execute(
                "SELECT * FROM fulfillment_door_units WHERE id=?",
                (door_unit_id,),
            ).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            package = connection.execute(
                """SELECT * FROM fulfillment_technical_packages
                   WHERE door_unit_id=? ORDER BY version DESC LIMIT 1""",
                (door_unit_id,),
            ).fetchone()
            if not package:
                raise LookupError("生产技术包不存在")
            if package["status"] != "草稿":
                raise RuntimeError("技术包已确认冻结，不能重新生成；请先发起生产变更创建新版本")
            cursor = connection.execute(
                """INSERT INTO fulfillment_bom_generation_runs(
                       order_id, door_unit_id, technical_package_id, rule_version,
                       started_at, created_by
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    door["order_id"], door_unit_id, package["id"], rule_version,
                    now, str(user.get("uid") or ""),
                ),
            )
            run_id = int(cursor.lastrowid)
            package_id = int(package["id"])
            order_id = int(door["order_id"])
            params = json_loads(package["product_snapshot_json"], {})

        try:
            items, rule_warnings = build_baseline_bom(params)
            with self.db.transaction() as connection:
                current = connection.execute(
                    "SELECT status FROM fulfillment_technical_packages WHERE id=?",
                    (package_id,),
                ).fetchone()
                if not current or current["status"] != "草稿":
                    raise RuntimeError("BOM生成期间技术包状态已变化，请刷新后重试")
                connection.execute(
                    """DELETE FROM fulfillment_components
                       WHERE technical_package_id=? AND source_type IN ('rule_generated','seed_default')""",
                    (package_id,),
                )
                base_line = int((connection.execute(
                    "SELECT COALESCE(MAX(line_no), 0) AS value FROM fulfillment_components WHERE technical_package_id=?",
                    (package_id,),
                ).fetchone() or {"value": 0})["value"] or 0)
                all_warnings: List[BomRuleWarning] = list(rule_warnings)
                matched_count = 0
                for sequence, item in enumerate(items, start=1):
                    material_id, match_status, match_warning = self._match_material(connection, item)
                    if match_warning:
                        all_warnings.append(match_warning)
                    if match_status == "已匹配":
                        matched_count += 1
                    planned_quantity = item.planned_quantity
                    connection.execute(
                        """INSERT INTO fulfillment_components(
                               technical_package_id, material_id, name, category, specification,
                               quantity, unit, acquisition_method, sequence_no, line_no, group_code,
                               theoretical_quantity, waste_rate, planned_quantity, source_type,
                               source_rule_version, source_payload_json, match_status,
                               verification_status, operation_code, required_date, attachments_json
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                     'rule_generated', ?, ?, ?, '待核验', ?, ?, '[]')""",
                        (
                            package_id, material_id, item.name, item.category, item.specification,
                            planned_quantity, item.unit, item.acquisition_method, base_line + sequence,
                            base_line + sequence, item.group_code, item.theoretical_quantity,
                            item.waste_rate, planned_quantity, rule_version,
                            json_dumps(item.source_payload), match_status, item.operation_code,
                            str(params.get("required_date") or ""),
                        ),
                    )

                for warning in all_warnings:
                    connection.execute(
                        """INSERT INTO fulfillment_bom_generation_warnings(
                               run_id, order_id, door_unit_id, technical_package_id,
                               rule_version, severity, field_path, code, message,
                               blocking, created_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run_id, order_id, door_unit_id, package_id, rule_version,
                            warning.severity, warning.field_path, warning.code,
                            warning.message, int(warning.blocking), now,
                        ),
                    )
                blocking_count = sum(1 for warning in all_warnings if warning.blocking)
                generation_status = "待完善" if blocking_count else "已生成"
                summary = {
                    "generated_count": len(items),
                    "matched_count": matched_count,
                    "warning_count": len(all_warnings),
                    "blocking_warning_count": blocking_count,
                    "group_counts": {
                        code: sum(1 for item in items if item.group_code == code)
                        for code in sorted({item.group_code for item in items})
                    },
                }
                connection.execute(
                    """UPDATE fulfillment_technical_packages
                       SET generation_status=?, rule_version=?, generated_at=?,
                           generation_summary_json=?, blocking_warning_count=?, updated_at=?
                       WHERE id=?""",
                    (
                        generation_status, rule_version, now, json_dumps(summary),
                        blocking_count, now, package_id,
                    ),
                )
                connection.execute(
                    """UPDATE fulfillment_bom_generation_runs
                       SET status='已完成', generated_count=?, matched_count=?,
                           warning_count=?, blocking_warning_count=?, completed_at=?
                       WHERE id=?""",
                    (len(items), matched_count, len(all_warnings), blocking_count, now, run_id),
                )
                self.db.add_event(
                    connection, order_id=order_id, door_unit_id=door_unit_id,
                    entity_type="technical_package", entity_id=package_id,
                    action="自动生成整樘BOM",
                    detail=f"规则 {rule_version}，生成 {len(items)} 项，待处理 {blocking_count} 项",
                    user=user,
                )
        except Exception as exc:
            failed_at = fulfillment_now()
            with self.db.transaction() as connection:
                connection.execute(
                    """UPDATE fulfillment_bom_generation_runs
                       SET status='失败', error_message=?, completed_at=? WHERE id=?""",
                    (str(exc)[:1000], failed_at, run_id),
                )
                connection.execute(
                    """UPDATE fulfillment_technical_packages
                       SET generation_status='生成失败', updated_at=? WHERE id=?""",
                    (failed_at, package_id),
                )
            raise
        return self.get_generation(package_id, run_id)

    def recalculate_frame(self, door_unit_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the draft package's frame assembly with canonical v1.4.3 parts."""

        from door_cad.services.fulfillment_adapter import calculate_fulfillment_frame

        adaptation, geometry = calculate_fulfillment_frame(self.db, door_unit_id)
        if geometry.validation.errors:
            message = "；".join(issue.message for issue in geometry.validation.errors)
            raise ValueError(message or "门框几何校验未通过")

        now = fulfillment_now()
        frame_rule_version = geometry.parts[0].process.sourceRule if geometry.parts else "frame-new-v1.4.3"
        with self.db.transaction() as connection:
            door = connection.execute(
                "SELECT * FROM fulfillment_door_units WHERE id=?",
                (door_unit_id,),
            ).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            package = connection.execute(
                """SELECT * FROM fulfillment_technical_packages
                   WHERE door_unit_id=? ORDER BY version DESC LIMIT 1""",
                (door_unit_id,),
            ).fetchone()
            if not package:
                raise LookupError("生产技术包不存在")
            if int(package["id"]) != adaptation.technicalPackageId:
                raise RuntimeError("门框计算期间技术包版本已变化，请刷新后重试")
            if package["status"] != "草稿":
                raise RuntimeError("技术包已确认冻结，不能重算门框；请先发起生产变更创建新版本")
            cursor = connection.execute(
                """INSERT INTO fulfillment_bom_generation_runs(
                       order_id, door_unit_id, technical_package_id, rule_version,
                       started_at, created_by
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    door["order_id"], door_unit_id, package["id"], frame_rule_version,
                    now, str(user.get("uid") or ""),
                ),
            )
            run_id = int(cursor.lastrowid)
            package_id = int(package["id"])
            order_id = int(door["order_id"])
            params = json_loads(package["product_snapshot_json"], {})
            package_rule_version = str(package["rule_version"] or CURRENT_BOM_RULE_VERSION)
            previous_summary = json_loads(package["generation_summary_json"], {})

        try:
            with self.db.transaction() as connection:
                current = connection.execute(
                    "SELECT status FROM fulfillment_technical_packages WHERE id=?",
                    (package_id,),
                ).fetchone()
                if not current or current["status"] != "草稿":
                    raise RuntimeError("门框回算期间技术包状态已变化，请刷新后重试")

                connection.execute(
                    """DELETE FROM fulfillment_components
                       WHERE technical_package_id=?
                         AND (source_type='frame_geometry' OR operation_code='FRAME_ASSEMBLY')""",
                    (package_id,),
                )
                base_line = int((connection.execute(
                    "SELECT COALESCE(MAX(line_no), 0) AS value FROM fulfillment_components WHERE technical_package_id=?",
                    (package_id,),
                ).fetchone() or {"value": 0})["value"] or 0)

                warnings: List[BomRuleWarning] = [
                    BomRuleWarning(
                        field_path=issue.field,
                        code=issue.code.lower(),
                        message=issue.message,
                        severity=issue.severity,
                        blocking=False,
                    )
                    for issue in adaptation.warnings
                ]
                warnings.extend(
                    BomRuleWarning(
                        field_path=issue.field or "frame_geometry",
                        code=issue.code.lower(),
                        message=issue.message,
                        severity=issue.severity,
                        blocking=False,
                    )
                    for issue in geometry.validation.warnings
                )
                matched_count = 0
                for sequence, part in enumerate(geometry.parts, start=1):
                    material_label = "骨架" if part.materialType == "skeleton" else "外皮"
                    item = BomRuleItem(
                        group_code="frame",
                        name=part.name,
                        specification=(
                            f"{material_label}; 长{part.length:g}; 展开{part.flatWidth:g}; "
                            f"厚{part.thickness:g}"
                        ),
                        theoretical_quantity=1,
                        unit="件",
                        operation_code="FRAME_PART",
                        acquisition_method="内部加工",
                        material_code=str(params.get(
                            "frame_skeleton_material_code"
                            if part.materialType == "skeleton"
                            else "frame_skin_material_code"
                        ) or params.get("frame_material_code") or ""),
                        source_payload={
                            "geometry_ref": f"{frame_rule_version}:{part.partId}",
                            "part_id": part.partId,
                            "position": part.position,
                            "material_type": part.materialType,
                            "length": part.length,
                            "flat_width": part.flatWidth,
                            "thickness": part.thickness,
                            "process": part.process.model_dump(mode="json"),
                        },
                    )
                    material_id, match_status, match_warning = self._match_material(connection, item)
                    if match_warning:
                        warnings.append(match_warning)
                    if match_status == "已匹配":
                        matched_count += 1
                    connection.execute(
                        """INSERT INTO fulfillment_components(
                               technical_package_id, material_id, name, category, specification,
                               quantity, unit, acquisition_method, sequence_no, line_no, group_code,
                               theoretical_quantity, waste_rate, planned_quantity, source_type,
                               source_rule_version, source_payload_json, match_status,
                               verification_status, operation_code, required_date, attachments_json
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'frame_geometry',
                                     ?, ?, ?, '待核验', ?, ?, '[]')""",
                        (
                            package_id, material_id, item.name, item.category, item.specification,
                            item.planned_quantity, item.unit, item.acquisition_method,
                            base_line + sequence, base_line + sequence, item.group_code,
                            item.theoretical_quantity, item.waste_rate, item.planned_quantity,
                            frame_rule_version, json_dumps(item.source_payload), match_status,
                            item.operation_code, str(params.get("required_date") or ""),
                        ),
                    )

                for warning in warnings:
                    connection.execute(
                        """INSERT INTO fulfillment_bom_generation_warnings(
                               run_id, order_id, door_unit_id, technical_package_id,
                               rule_version, severity, field_path, code, message,
                               blocking, created_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run_id, order_id, door_unit_id, package_id, frame_rule_version,
                            warning.severity, warning.field_path, warning.code, warning.message,
                            int(warning.blocking), now,
                        ),
                    )

                unresolved_count = int((connection.execute(
                    """SELECT COUNT(*) AS value FROM fulfillment_components
                       WHERE technical_package_id=?
                         AND source_type IN ('rule_generated','frame_geometry')
                         AND match_status IN ('待匹配','匹配冲突','缺少资料')""",
                    (package_id,),
                ).fetchone() or {"value": 0})["value"] or 0)
                generation_status = "待完善" if unresolved_count else "已生成"
                summary = dict(previous_summary)
                summary["frame"] = {
                    "rule_version": frame_rule_version,
                    "part_count": len(geometry.parts),
                    "matched_count": matched_count,
                    "warning_count": len(warnings),
                    "calculated_at": now,
                }
                connection.execute(
                    """UPDATE fulfillment_technical_packages
                       SET generation_status=?, rule_version=?, generated_at=?,
                           generation_summary_json=?, blocking_warning_count=?, updated_at=?
                       WHERE id=?""",
                    (
                        generation_status, package_rule_version, now, json_dumps(summary),
                        unresolved_count, now, package_id,
                    ),
                )
                blocking_count = sum(1 for warning in warnings if warning.blocking)
                connection.execute(
                    """UPDATE fulfillment_bom_generation_runs
                       SET status='已完成', generated_count=?, matched_count=?,
                           warning_count=?, blocking_warning_count=?, completed_at=?
                       WHERE id=?""",
                    (
                        len(geometry.parts), matched_count, len(warnings),
                        blocking_count, now, run_id,
                    ),
                )
                self.db.add_event(
                    connection, order_id=order_id, door_unit_id=door_unit_id,
                    entity_type="technical_package", entity_id=package_id,
                    action="重算门框加工BOM",
                    detail=(
                        f"规则 {frame_rule_version}，生成 {len(geometry.parts)} 个门框零件，"
                        f"整樘BOM待处理 {unresolved_count} 项"
                    ),
                    user=user,
                )
        except Exception as exc:
            failed_at = fulfillment_now()
            with self.db.transaction() as connection:
                connection.execute(
                    """UPDATE fulfillment_bom_generation_runs
                       SET status='失败', error_message=?, completed_at=? WHERE id=?""",
                    (str(exc)[:1000], failed_at, run_id),
                )
            raise
        return self.get_generation(package_id, run_id)

    def get_generation(self, package_id: int, run_id: Optional[int] = None) -> Dict[str, Any]:
        package = self.db.fetch_one(
            "SELECT * FROM fulfillment_technical_packages WHERE id=?",
            (package_id,),
        )
        if not package:
            raise LookupError("生产技术包不存在")
        if run_id is None:
            run = self.db.fetch_one(
                """SELECT * FROM fulfillment_bom_generation_runs
                   WHERE technical_package_id=? ORDER BY id DESC LIMIT 1""",
                (package_id,),
            )
            run_id = int(run["id"]) if run else -1
        components = self.db.fetch_all(
            """SELECT * FROM fulfillment_components
               WHERE technical_package_id=? ORDER BY line_no, id""",
            (package_id,),
        )
        for component in components:
            component["source_payload"] = json_loads(component.pop("source_payload_json", ""), {})
            component["attachments"] = json_loads(component.pop("attachments_json", ""), [])
        warnings = self.db.fetch_all(
            """SELECT * FROM fulfillment_bom_generation_warnings
               WHERE run_id=? ORDER BY blocking DESC, id""",
            (run_id,),
        )
        summary = json_loads(package.get("generation_summary_json"), {})
        return {
            "technical_package_id": package_id,
            "door_unit_id": int(package["door_unit_id"]),
            "version": int(package["version"]),
            "generation_status": package["generation_status"],
            "rule_version": package["rule_version"],
            "generated_at": package["generated_at"],
            "blocking_warning_count": int(package["blocking_warning_count"] or 0),
            "summary": summary,
            "components": components,
            "warnings": warnings,
        }
