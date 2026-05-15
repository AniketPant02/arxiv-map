"""Geocoding provider and cache scaffolds."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import Engine


class GeocoderProvider(Protocol):
    """Protocol for live geocoding providers."""

    def geocode(self, query: str) -> dict[str, Any] | None:
        """Return a provider-specific geocode result for a query."""
        raise NotImplementedError


class CachedGeocoder:
    """Use the institutions table as a geocoding cache."""

    def __init__(self, engine: Engine, provider: GeocoderProvider | None = None) -> None:
        self.engine = engine
        self.provider = provider

    def get_pending_institutions(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return institutions that still need geocoding."""
        raise NotImplementedError

    def update_cache(self, institution_key: str, geocode_result: dict[str, Any]) -> None:
        """Update cached geocoding fields for an institution."""
        raise NotImplementedError

    def geocode_live(self, query: str) -> dict[str, Any] | None:
        """Call the configured live geocoder provider."""
        raise NotImplementedError
