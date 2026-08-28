"""Door-frame cutting API router."""

from fastapi import APIRouter

from door_cad.api import frame_router, projects_router


router = APIRouter(prefix="/api/door-cad/frame", tags=["door-frame-cutting"])
router.include_router(frame_router)
router.include_router(projects_router)
