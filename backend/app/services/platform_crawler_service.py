"""Platform crawler service facade.

The implementation was split by responsibility into:

- ``platform_crawler_account_service`` -- benchmark account parsing and CRUD.
- ``platform_crawler_feed_service`` -- feed simulation and account-post fetching.
- ``platform_crawler_collect_service`` -- batch collect and deconstruction pipeline.
- ``platform_crawler_support_service`` -- shared module-level helpers.

This module keeps the historical public surface unchanged: ``PlatformCrawlerService``,
``_parse_uid`` and ``extract_fallback_blueprint`` remain importable from here.
"""

from __future__ import annotations

from app.services.platform_crawler_account_service import (
    PlatformCrawlerAccountMixin,
)
from app.services.platform_crawler_collect_service import (
    PlatformCrawlerCollectMixin,
)
from app.services.platform_crawler_feed_service import PlatformCrawlerFeedMixin
from app.services.platform_crawler_support_service import (
    _parse_uid,
    extract_fallback_blueprint,
)

__all__ = [
    "PlatformCrawlerService",
    "_parse_uid",
    "extract_fallback_blueprint",
]


class PlatformCrawlerService(
    PlatformCrawlerAccountMixin,
    PlatformCrawlerFeedMixin,
    PlatformCrawlerCollectMixin,
):
    """Facade over the split platform crawler mixins."""
