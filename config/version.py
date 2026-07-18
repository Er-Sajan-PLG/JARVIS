# Deprecated stub.
#
# The canonical version now lives in `app/config/version.py` and is derived
# AUTOMATICALLY from git tags (vA.B.C). It is no longer hardcoded here.
# This file only re-exports it so any accidental legacy import keeps working.
from app.config.version import (  # noqa: F401
    VERSION,
    get_version_info,
    MAJOR,
    MINOR,
    PATCH,
    BASE_TAG,
    COMMITS_SINCE_TAG,
    GIT_HASH,
    DIRTY,
    IS_RELEASE,
    VERSION_SOURCE,
)
