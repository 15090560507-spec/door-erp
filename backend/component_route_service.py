"""Explicit component applicability and dependency-preserving template routes."""

import json


DEFAULT_GROUPS = {
    "PANEL_PREP": ["skin", "skeleton"], "PANEL_CUT": ["skin", "skeleton"],
    "BENDING": ["skin"], "BODY": ["skeleton"], "SURFACE": ["skin"],
    "ASSEMBLY": ["assembly"], "PACKAGING": ["packaging"],
}
GROUPS = {"skin", "skeleton", "assembly", "packaging", "other"}
BUSINESS_STAGES = {"TECH_PREP", "FITTINGS_PREP", "QC_HANDOFF"}


def validate_steps(steps):
    from door_piecework_service import money_cents

    codes = [step.step_code for step in steps]
    if any(not code.strip() or code != code.strip() for code in codes):
        raise ValueError("工序编码不能为空或包含首尾空格")
    if len(codes) != len(set(codes)):
        raise ValueError("工序编码不能重复")
    by_code = {step.step_code: step for step in steps}
    visiting, visited = set(), set()

    def visit(code):
        if code in visiting:
            raise ValueError("工序前序存在循环依赖")
        if code in visited:
            return
        visiting.add(code)
        for predecessor in by_code[code].predecessor_codes:
            if predecessor not in by_code:
                raise ValueError(f"前序工序不存在：{predecessor}")
            if by_code[code].is_active and not by_code[predecessor].is_active:
                raise ValueError("启用工序不能依赖停用工序")
            visit(predecessor)
        visiting.remove(code)
        visited.add(code)

    for step in steps:
        if not step.name.strip():
            raise ValueError("工序名称不能为空")
        if not set(step.applicable_groups).issubset(GROUPS):
            raise ValueError("工序适用部件组无效")
        money_cents(step.piece_rate)
        visit(step.step_code)


def component_group(component):
    code = str(component["operation_code"] or "").upper()
    if component["item_kind"] == "assembly":
        return "assembly"
    if "SKIN" in code or "SHEET" in code:
        return "skin"
    if "SKELETON" in code or "PROFILE" in code:
        return "skeleton"
    return "packaging" if code == "PACKAGING" else "other"


def component_route(conn, component):
    from work_package_service import RouteNode, WorkPackageService

    group = component_group(component)
    template = conn.execute("SELECT * FROM process_route_templates WHERE is_active=1 AND target_group='door' ORDER BY is_default DESC,id LIMIT 1").fetchone()
    if not template:
        return [RouteNode(**{**vars(node), "snapshot": {"process_unconfigured": True}}) for node in WorkPackageService._component_route(component)]
    rows = conn.execute("SELECT * FROM process_route_template_steps WHERE template_id=? AND is_active=1 ORDER BY sequence_no,id", (template["id"],)).fetchall()
    by_code = {row["step_code"]: row for row in rows}
    selected = {row["step_code"] for row in rows if row["step_code"] not in BUSINESS_STAGES and group in json.loads(row["applicable_groups_json"])}
    if not selected:
        return [RouteNode(**{**vars(node), "snapshot": {"process_unconfigured": True}}) for node in WorkPackageService._component_route(component)]

    def nearest(code, seen=frozenset()):
        if code in selected:
            return [code]
        if code not in by_code or code in seen:
            return []
        return list(dict.fromkeys(p for parent in json.loads(by_code[code]["predecessor_codes_json"]) for p in nearest(parent, seen | {code})))

    aliases = {"PANEL_PREP": "PREPARE", "PANEL_CUT": "SHEAR" if group == "skin" else "CUT", "BENDING": "BEND", "BODY": "WELD", "PACKAGING": "PROCESS"}
    execution = {code: aliases.get(code, code) for code in selected}
    if len(set(execution.values())) != len(execution):
        raise ValueError("适用工序的执行编码重复，请调整模板编码")
    nodes = []
    for row in rows:
        code = row["step_code"]
        if code not in selected:
            continue
        predecessors = list(dict.fromkeys(p for parent in json.loads(row["predecessor_codes_json"]) for p in nearest(parent)))
        snapshot = {
            "template_code": template["code"], "template_version": template["version"],
            "billing_operation_code": code, "name": row["name"],
            "applicable_groups": json.loads(row["applicable_groups_json"]),
            "predecessors": predecessors, "piece_rate": str(row["piece_rate"]),
            "inspection_required": bool(row["inspection_required"]),
            "standard_minutes": row["standard_minutes"], "default_role": row["default_role"],
            "work_center": row["work_center"], "component_group": group,
        }
        nodes.append(RouteNode(
            code=execution[code], name=row["name"], category=row["category"], weight=row["weight"],
            predecessors=tuple(execution[p] for p in predecessors),
            inspection_required=bool(row["inspection_required"]), template_id=template["id"],
            template_step_id=row["id"], standard_minutes=row["standard_minutes"],
            default_role=row["default_role"], work_center=row["work_center"], snapshot=snapshot,
        ))
    # The template list need not already be topologically ordered.
    ordered = []
    while nodes:
        ready = [node for node in nodes if set(node.predecessors).issubset({n.code for n in ordered})]
        if not ready:
            raise ValueError("适用工序存在循环依赖")
        ordered.extend(ready)
        nodes = [node for node in nodes if node not in ready]
    return ordered
