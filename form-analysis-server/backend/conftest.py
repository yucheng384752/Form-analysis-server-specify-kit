# This conftest controls *collection only* for the backend project.
#
# The repository contains many legacy/manual scripts and scratch files in the
# backend root (and under scripts/tools). These are not part of the supported
# pytest suite (which lives under ./tests) and can break collection when pytest
# is invoked from different working directories.

# Directories that should never be collected as tests.
collect_ignore = [
    "project-reports",
    "scripts",
    "tools",
    # Legacy/scratch tests kept in backend root (not under ./tests)
    "test_advanced_search.py",
    "test_api.py",
    "test_api_upload.py",
    "test_constants_api.py",
    "test_import_export_api.py",
    "test_integration.py",
    "test_integration_full_flow.py",
    "test_lot_no_regex.py",
    "test_models.py",
    "test_new_architecture.py",
    "test_new_p3_format.py",
    "test_product_id.py",
    "test_schemas.py",
    "test_traceability_api.py",
    "test_upload_functionality.py",
    "test_validate_api.py",
]
