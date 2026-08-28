"""Application services for deterministic door-frame geometry."""

from .frame_calculator import calculate_frame_project
from .validation import requires_warning_acknowledgement, validate_project_geometry
from .bom import BomRow, build_bom_rows

__all__ = [
    "calculate_frame_project",
    "requires_warning_acknowledgement",
    "validate_project_geometry",
    "BomRow",
    "build_bom_rows",
]
