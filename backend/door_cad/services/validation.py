"""Production-oriented validation for the canonical door-frame geometry."""

from __future__ import annotations

import hashlib
from collections import Counter

from door_cad.baseline import BASELINE_DIR, load_json_fixture
from door_cad.geometry import has_duplicate_adjacent_points
from door_cad.models import (
    PartGeometry,
    Point2D,
    ProjectGeometry,
    ValidationIssue,
    ValidationReport,
)


def _issue(code: str, message: str, field: str | None, severity: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, field=field, severity=severity)


def _orientation(a: Point2D, b: Point2D, c: Point2D) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _has_strict_self_intersection(part: PartGeometry) -> bool:
    points = part.cutOuter.points
    edges = list(zip(points, points[1:] + points[:1]))
    for first_index, (a, b) in enumerate(edges):
        for second_index in range(first_index + 1, len(edges)):
            if second_index in (first_index, first_index + 1):
                continue
            if first_index == 0 and second_index == len(edges) - 1:
                continue
            c, d = edges[second_index]
            if _orientation(a, b, c) * _orientation(a, b, d) < -1e-8 and _orientation(c, d, a) * _orientation(c, d, b) < -1e-8:
                return True
    return False


def _bounds(part: PartGeometry) -> tuple[float, float, float, float]:
    xs = [point.x for point in part.cutOuter.points]
    ys = [point.y for point in part.cutOuter.points]
    return min(xs), max(xs), min(ys), max(ys)


def _shape_bounds(shape) -> tuple[float, float, float, float] | None:
    if shape.center is not None:
        width = shape.diameter if shape.diameter is not None else shape.width or 0
        height = shape.diameter if shape.diameter is not None else shape.height or 0
        return (
            shape.center.x - width / 2,
            shape.center.x + width / 2,
            shape.center.y - height / 2,
            shape.center.y + height / 2,
        )
    if shape.points:
        xs = [point.x for point in shape.points]
        ys = [point.y for point in shape.points]
        return min(xs), max(xs), min(ys), max(ys)
    return None


def _validate_part(part: PartGeometry, errors: list[ValidationIssue]) -> None:
    field = f"parts.{part.partId}"
    if has_duplicate_adjacent_points(part.cutOuter):
        errors.append(_issue("DUPLICATE_CUT_POINT", f"{part.name}切割轮廓存在重复相邻点", field, "error"))
    if _has_strict_self_intersection(part):
        errors.append(_issue("SELF_INTERSECTING_CUT", f"{part.name}切割轮廓自交", field, "error"))

    min_x, max_x, min_y, max_y = _bounds(part)
    section_xs = [point.x for point in part.flatSection.points]
    if abs((max(section_xs) - min(section_xs)) - part.flatWidth) > 0.01:
        errors.append(_issue("CHAIN_SUM_MISMATCH", f"{part.name}展开链宽与零件宽度不一致", field, "error"))

    for shape in part.holes:
        bounds = _shape_bounds(shape)
        if bounds and (bounds[0] < min_x - 0.01 or bounds[1] > max_x + 0.01 or bounds[2] < min_y - 0.01 or bounds[3] > max_y + 0.01):
            errors.append(_issue("HOLE_OUTSIDE_MATERIAL", f"{part.name}孔位 {shape.shapeId} 超出材料边界", field, "error"))
    for groove in part.grooves:
        for segment in groove.segments:
            for value in (segment.start, segment.end):
                if value.x < min_x - 0.01 or value.x > max_x + 0.01 or value.y < min_y - 0.01 or value.y > max_y + 0.01:
                    errors.append(_issue("GROOVE_OUTSIDE_MATERIAL", f"{part.name}槽线 {groove.grooveId} 超出材料边界", field, "error"))
                    break

    should_mirror = part.position == "right" or part.partId.startswith("BF-")
    if part.process.mirrored != should_mirror:
        errors.append(_issue("MIRROR_SEMANTICS", f"{part.name}镜像标记与零件方向不一致", field, "error"))

    if part.materialType == "skin" and part.position in ("left", "right"):
        clipped = [
            segment
            for groove in part.grooves
            for segment in groove.segments
            if segment.start.y > 0.01 or segment.end.y < part.length - 0.01
        ]
        if not clipped:
            errors.append(_issue("NOTCH_GROOVE_NOT_CLIPPED", f"{part.name}端部异形区槽线未避让", field, "error"))


def _template_warnings() -> list[ValidationIssue]:
    warnings: list[ValidationIssue] = []
    expected = load_json_fixture("v143_template_checksums.json")
    for filename, checksum in expected.items():
        path = BASELINE_DIR / filename
        if not path.exists():
            warnings.append(_issue("TEMPLATE_MISSING", f"冻结模板不存在：{filename}", "templates", "warning"))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            warnings.append(_issue("TEMPLATE_CHECKSUM_CHANGED", f"冻结模板校验和已变化：{filename}", "templates", "warning"))
    return warnings


def validate_project_geometry(geometry: ProjectGeometry) -> ValidationReport:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    part_ids = [part.partId for part in geometry.parts]
    duplicate_ids = [part_id for part_id, count in Counter(part_ids).items() if count > 1]
    if duplicate_ids:
        errors.append(_issue("DUPLICATE_PART_ID", f"零件编号重复：{', '.join(duplicate_ids)}", "parts", "error"))

    expected_count = 2 * sum((geometry.inputs.includeLeft, geometry.inputs.includeRight, geometry.inputs.includeTop, geometry.inputs.includeBottom))
    if len(geometry.parts) != expected_count:
        errors.append(_issue("BOM_PART_COUNT", f"应生成 {expected_count} 个零件，实际 {len(geometry.parts)} 个", "parts", "error"))
    if len(geometry.assembly.placements) != len(geometry.parts):
        errors.append(_issue("ASSEMBLY_PART_COUNT", "装配位置数量与零件数量不一致", "assembly", "error"))

    for part in geometry.parts:
        _validate_part(part, errors)

    inputs = geometry.inputs
    if (inputs.outerSideShort, inputs.outerSideLong) != (55.0, 62.0):
        warnings.append(_issue("NON_STANDARD_SIDE_SIZE", "左右框不是已确认的标准 55/62 尺寸", "outerSideShort", "warning"))
    if (inputs.topShort, inputs.topLong) != (55.0, 75.0):
        warnings.append(_issue("NON_STANDARD_TOP_SIZE", "上框不是已确认的标准 55/75 尺寸", "topShort", "warning"))
    bottom_sizes = inputs.resolved_bottom_sizes()
    if bottom_sizes != (55.0, 75.0):
        warnings.append(_issue("NON_STANDARD_BOTTOM_SIZE", "下框不是已确认的标准 55/75 尺寸", "bottomShort", "warning"))
    if not geometry.project.projectName.strip():
        warnings.append(_issue("PROJECT_NAME_MISSING", "项目名称为空，导出文件不便追溯", "project.projectName", "warning"))
    warnings.extend(_template_warnings())

    status = "ERROR" if errors else "WARNING" if warnings else "PASSED"
    return ValidationReport(status=status, errors=errors, warnings=warnings)


def requires_warning_acknowledgement(report: ValidationReport, acknowledged: bool) -> bool:
    """Exports may use this without changing the calculation result itself."""

    return bool(report.warnings) and not acknowledged
