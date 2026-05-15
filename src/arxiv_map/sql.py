"""SQL functions for uploading arxiv data"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import Engine, create_engine


class ArxivMapSQLClient:
    """Notebook-friendly SQL client for project upload workflows."""

    def __init__(self, database_url: str | None = None, engine: Engine | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.engine = engine or create_engine(self.database_url)

    def upload_papers(self, paper_rows: list[dict[str, Any]]) -> None:
        """Upload or update paper rows."""
        raise NotImplementedError

    def upload_authors(self, author_rows: list[dict[str, Any]]) -> None:
        """Upload or update paper author rows."""
        raise NotImplementedError

    def upload_institutions(self, institution_rows: list[dict[str, Any]]) -> None:
        """Upload or update institution rows."""
        raise NotImplementedError

    def upload_links(self, link_rows: list[dict[str, Any]]) -> None:
        """Upload or update paper-author-institution link rows."""
        raise NotImplementedError

    def refresh_network(self, concurrently: bool = False) -> None:
        """Refresh materialized network views."""
        raise NotImplementedError
