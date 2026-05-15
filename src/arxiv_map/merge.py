"""
Merging COMET and arxiv data into normalized rows, in prep for SQL upload
"""

from __future__ import annotations

from typing import Any


class CometArxivMerger:
    """Build normalized project records from COMET and arXiv inputs."""

    def merge(
        self,
        comet_rows: list[dict[str, Any]],
        arxiv_metadata_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Given matched COMET and arxiv source rows, produce merged output rows. This assumes matching rows are provided as input.
        """
        raise NotImplementedError
