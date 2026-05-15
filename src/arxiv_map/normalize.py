"""Normalization scaffolds for project data."""

from __future__ import annotations

from typing import Any


class Normalizer:
    """Normalize arXiv IDs, names, text, and institution identifiers."""

    def arxiv_id(self, raw_id: str) -> str:
        """Normalize an arXiv ID into the database key format."""
        raise NotImplementedError

    def author_name(self, raw_name: str) -> str:
        """Normalize an author name for matching and storage."""
        raise NotImplementedError

    def institution_key(self, affiliation: dict[str, Any]) -> str:
        """Build a stable institution key from an affiliation record."""
        raise NotImplementedError

    def affiliation(self, raw_affiliation: str | None) -> str | None:
        """Normalize a raw affiliation string."""
        raise NotImplementedError

    def text(self, raw_text: str | None) -> str | None:
        """Normalize free-form text fields."""
        raise NotImplementedError