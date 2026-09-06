from __future__ import annotations

from typing import Protocol

from vesivek.models import SiteFrame


class WfsFetcher(Protocol):
    name: str

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        """Return a TM35FIN site frame or None if this source has no hit."""
