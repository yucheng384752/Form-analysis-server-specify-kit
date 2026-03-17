"""Analytics API package.

Creates a router with prefix="/api/v2/analytics" and includes sub-routers
for flatten, artifacts, and analysis endpoints.
"""

from fastapi import APIRouter

from .routes_analysis import router as analysis_router
from .routes_artifacts import router as artifacts_router
from .routes_flatten import router as flatten_router

router = APIRouter(prefix="/api/v2/analytics")
router.include_router(flatten_router)
router.include_router(artifacts_router)
router.include_router(analysis_router)
