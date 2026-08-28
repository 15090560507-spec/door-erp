"""BOM projection from canonical door-frame geometry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from door_cad.models import ProjectGeometry


class BomRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partId: str
    name: str
    position: str
    materialType: str
    length: float = Field(gt=0)
    flatWidth: float = Field(gt=0)
    thickness: float = Field(gt=0)
    quantity: int = 1
    notes: str = ""


POSITION_LABELS = {"left": "左框", "right": "右框", "top": "上框", "bottom": "下框"}
MATERIAL_LABELS = {"skeleton": "骨架", "skin": "外皮"}


def build_bom_rows(geometry: ProjectGeometry) -> list[BomRow]:
    return [
        BomRow(
            partId=part.partId,
            name=part.name,
            position=POSITION_LABELS.get(part.position, part.position),
            materialType=MATERIAL_LABELS.get(part.materialType, part.materialType),
            length=part.length,
            flatWidth=part.flatWidth,
            thickness=part.thickness,
            quantity=1,
            notes="；".join(part.process.notes),
        )
        for part in geometry.parts
    ]
