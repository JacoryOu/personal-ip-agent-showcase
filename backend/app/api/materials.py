# -*- coding: utf-8 -*-
"""Compatibility facade for the Materials API.

Shared helpers live in `app.api.materials_common`; the route handlers are
split across `app.api.materials_crud`, `app.api.materials_collect` and
`app.api.materials_item`. The `materials` blueprint name, every route path and
every previously importable public symbol are preserved.
"""

from app.api.materials_common import *  # noqa: F401,F403
from app.api.materials_common import (  # noqa: F401
    MATERIAL_NOT_FOUND_MESSAGE,
    _get_owned_material,
    _parse_uid,
    _serialize_material,
    router,
)

from app.api.materials_crud import (  # noqa: F401
    create_material,
    list_materials,
)
from app.api.materials_collect import (  # noqa: F401
    collect_url,
    fetch_trending,
)
from app.api.materials_item import (  # noqa: F401
    delete_material,
    get_material,
    update_material,
)

__all__ = [
    'MATERIAL_NOT_FOUND_MESSAGE',
    '_get_owned_material',
    '_parse_uid',
    '_serialize_material',
    'collect_url',
    'create_material',
    'delete_material',
    'fetch_trending',
    'get_material',
    'list_materials',
    'router',
    'update_material',
]
