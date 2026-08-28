"""Door-frame cutting API router."""

from fastapi import APIRouter

from door_cad.api import bom_router, dxf_router, frame_router, projects_router


router = APIRouter(prefix="/api/door-cad/frame", tags=["door-frame-cutting"])
router.include_router(frame_router)
router.include_router(projects_router)
router.include_router(dxf_router)
router.include_router(bom_router)
