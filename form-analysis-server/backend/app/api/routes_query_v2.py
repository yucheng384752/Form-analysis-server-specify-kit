"""Thin shim: keeps ``from app.api.routes_query_v2 import router`` working
so that ``main.py`` does not need any changes.

The actual implementation now lives in the ``app.api.query_v2`` package.
"""

from app.api.query_v2 import router  # noqa: F401

# Re-export helper used by tests.
from app.api.query_v2.helpers import _normalize_production_date  # noqa: F401
