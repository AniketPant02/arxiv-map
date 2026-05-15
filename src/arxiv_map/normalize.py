"""Normalization functions for various data properties"""

from __future__ import annotations

import re
from typing import Any

class Normalizer:
    """Normalize arXiv IDs, names, text, and institution identifiers."""

    def arxiv_id(self, raw_id: str) -> str:
        """Normalize an arXiv ID into the database key format."""
        arxiv_id = raw_id.removeprefix("arXiv:").strip()
        return re.sub(r"v\d+$", "", arxiv_id)

    def author_name(self, raw_name: str) -> str:
        """Normalize an author name for matching and storage."""
        return re.sub(r"\s+", " ", raw_name).strip().lower()

    def institution_key(self, affiliation: dict[str, Any]) -> str:
        """Build a stable institution key from an affiliation record."""
        ror_id = affiliation.get("ror_id")
        if ror_id:
            return "ror:" + ror_id.rstrip("/").split("/")[-1]
        
        def slugify(text: str) -> str:
            text = text.lower().strip()
            text = re.sub(r"[^a-z0-9]+", "-", text)
            return text

        return "raw:" + slugify(affiliation.get("affiliation", ""))

    def affiliation(self, raw_affiliation: str | None) -> str | None:
        """Normalize a raw affiliation string."""
        if not raw_affiliation:
            return None
        text = re.sub(r"\s+", " ", raw_affiliation).strip()
        text = text.strip(",;.")
        return text or None

    def text(self, raw_text: str | None) -> str | None:
        """Normalize free-form text fields."""
        raise NotImplementedError