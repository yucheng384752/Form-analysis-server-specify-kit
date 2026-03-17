from fastapi import APIRouter

from .routes_dynamic import router as dynamic_router
from .routes_lots import router as lots_router
from .routes_misc import router as misc_router
from .routes_records import router as records_router

router = APIRouter()

# Include sub-routers (no prefix — prefix is set at main.py level)
router.include_router(lots_router)
router.include_router(records_router)
router.include_router(misc_router)
router.include_router(dynamic_router)

# Re-export helpers that external code may import directly from
# the old routes_query_v2 module (e.g. tests).
from .helpers import _normalize_production_date  # noqa: E402, F401
