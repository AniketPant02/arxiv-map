"""
Merging COMET and arxiv data into normalized rows, in prep for SQL upload
"""

from __future__ import annotations

import logging
from typing import Any

from .normalize import Normalizer

logger = logging.getLogger(__name__)


class CometArxivMerger:
    """Build normalized project records from COMET and arXiv inputs."""

    def __init__(self) -> None:
        self.normalizer = Normalizer()

    def merge(
        self,
        comet_rows: list[dict[str, Any]],
        arxiv_metadata_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Inner-join COMET and arXiv rows on normalized arXiv ID.

        Only rows whose arXiv ID appears in **both** inputs are included in
        the output.  Warnings are logged for IDs present in only one dataset.

        Returns one dict per matched ID with:
          - arxiv_id:         normalized arXiv ID (no prefix, no version suffix)
          - doi:              DOI from COMET row
          - version:          version string from COMET row
          - authors:          list of author dicts, each with normalized name,
                              display name, institution keys, and affiliations
          - arxiv_metadata:   the full arXiv metadata dict
          - title:            paper title from arXiv
          - abstract:         abstract from arXiv
          - categories:       list of {name, is_primary} dicts from arXiv
        """
        # Build a lookup of COMET rows keyed by normalized arXiv ID
        comet_by_id: dict[str, dict[str, Any]] = {}
        for row in comet_rows:
            arxiv_id = self.normalizer.arxiv_id(row.get("arxiv_id", ""))
            comet_by_id[arxiv_id] = row

        comet_ids = set(comet_by_id.keys())
        arxiv_ids = set(arxiv_metadata_by_id.keys())

        # Warn about IDs in only one dataset
        comet_only = comet_ids - arxiv_ids
        arxiv_only = arxiv_ids - comet_ids

        if comet_only:
            logger.warning(
                "Skipping %d IDs found in COMET only (not in arXiv metadata): %s",
                len(comet_only),
                sorted(comet_only),
            )
        if arxiv_only:
            logger.warning(
                "Skipping %d IDs found in arXiv metadata only (not in COMET): %s",
                len(arxiv_only),
                sorted(arxiv_only),
            )

        # Inner join: only process IDs present in both
        matched_ids = comet_ids & arxiv_ids
        merged: list[dict[str, Any]] = []

        for arxiv_id in sorted(matched_ids):
            comet_row = comet_by_id[arxiv_id]
            arxiv_meta = arxiv_metadata_by_id[arxiv_id]

            authors = []
            for prediction in comet_row.get("prediction", []):
                raw_name = prediction.get("name", "")
                affiliations = prediction.get("affiliations", [])
                authors.append({
                    "raw_name": raw_name,
                    "normalized_name": self.normalizer.author_name(raw_name),
                    "affiliations": [
                        {
                            "raw_affiliation": aff.get("affiliation"),
                            "normalized_affiliation": self.normalizer.affiliation(aff.get("affiliation")),
                            "ror_id": aff.get("ror_id"),
                            "institution_key": self.normalizer.institution_key(aff),
                        }
                        for aff in affiliations
                    ],
                })

            # Parse categories into list with primary flag
            cat_str = arxiv_meta.get("categories", "")
            cat_list = cat_str.split() if cat_str else []
            categories = [
                {"name": cat, "is_primary": i == 0}
                for i, cat in enumerate(cat_list)
            ]

            row: dict[str, Any] = {
                "arxiv_id": arxiv_id,
                "doi": comet_row.get("doi"),
                "version": comet_row.get("version"),
                "authors": authors,
                "arxiv_metadata": arxiv_meta,
                "title": (arxiv_meta.get("title") or "").replace("\n", " ").strip(),
                "abstract": (arxiv_meta.get("abstract") or "").strip(),
                "categories": categories,
            }
            merged.append(row)

        logger.info(
            "Merge complete: %d matched, %d COMET-only, %d arXiv-only",
            len(merged),
            len(comet_only),
            len(arxiv_only),
        )

        return merged

