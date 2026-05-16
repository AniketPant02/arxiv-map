"""SQL helpers for uploading arXiv map data.

The client is intentionally notebook-friendly: it accepts plain dictionaries
from the research notebooks, normalizes the fields that are easy to drift on,
and uses idempotent PostgreSQL upserts so cells can be re-run safely.
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.types import Text

from .normalize import Normalizer

DatabaseRow = Mapping[str, Any]


@dataclass(frozen=True)
class UploadSummary:
    """Small count summary for notebook display/logging."""

    papers: int = 0
    authors: int = 0
    institutions: int = 0
    links: int = 0


class ArxivMapSQLClient:
    """Notebook-friendly SQL client for project upload workflows."""

    def __init__(
        self, database_url: str | None = None, engine: Engine | None = None
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if engine is None and not self.database_url:
            raise ValueError(
                "Pass database_url or set the DATABASE_URL environment variable"
            )

        self.engine = engine or create_engine(self.database_url)
        self.normalizer = Normalizer()

    def upload_papers(self, paper_rows: Sequence[DatabaseRow]) -> UploadSummary:
        """Upload or update paper rows."""
        rows = [self._paper_row(row) for row in paper_rows]
        with self.engine.begin() as conn:
            self._upload_papers(conn, rows)
        return UploadSummary(papers=len(rows))

    def upload_authors(self, author_rows: Sequence[DatabaseRow]) -> UploadSummary:
        """Upload or update paper author rows."""
        rows = [self._author_row(row) for row in author_rows]
        with self.engine.begin() as conn:
            self._upload_authors(conn, rows)
        return UploadSummary(authors=len(rows))

    def upload_institutions(
        self, institution_rows: Sequence[DatabaseRow]
    ) -> UploadSummary:
        """Upload or update institution rows."""
        rows = [self._institution_row(row) for row in institution_rows]
        with self.engine.begin() as conn:
            self._upload_institutions(conn, rows)
        return UploadSummary(institutions=len(rows))

    def upload_links(self, link_rows: Sequence[DatabaseRow]) -> UploadSummary:
        """Upload or update paper-author-institution link rows."""
        rows = [self._link_row(row) for row in link_rows]
        with self.engine.begin() as conn:
            self._upload_links(conn, rows)
        return UploadSummary(links=len(rows))

    def refresh_network(self, concurrently: bool = False) -> None:
        """Refresh materialized network views."""
        function_name = (
            "refresh_arxiv_network_concurrently"
            if concurrently
            else "refresh_arxiv_network"
        )

        if concurrently:
            with self.engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as conn:
                conn.execute(text(f"SELECT {function_name}();"))
            return

        with self.engine.begin() as conn:
            conn.execute(text(f"SELECT {function_name}();"))

    def upload_merged_rows(
        self,
        merged_rows: Sequence[DatabaseRow],
        *,
        refresh_network: bool = False,
        refresh_concurrently: bool = False,
    ) -> UploadSummary:
        """
        Upload rows returned by :class:`arxiv_map.merge.CometArxivMerger`.
        """
        rows = self.rows_from_merged(merged_rows)
        paper_rows = [self._paper_row(row) for row in rows["papers"]]
        author_rows = [self._author_row(row) for row in rows["authors"]]
        institution_rows = [self._institution_row(row) for row in rows["institutions"]]
        link_rows = [self._link_row(row) for row in rows["links"]]
        summary = UploadSummary(
            papers=len(paper_rows),
            authors=len(author_rows),
            institutions=len(institution_rows),
            links=len(link_rows),
        )

        with self.engine.begin() as conn:
            self._upload_papers(conn, paper_rows)
            self._upload_authors(conn, author_rows)
            self._upload_institutions(conn, institution_rows)
            self._upload_links(conn, link_rows)

        if refresh_network:
            self.refresh_network(concurrently=refresh_concurrently)

        return summary

    def rows_from_merged(
        self, merged_rows: Sequence[DatabaseRow]
    ) -> dict[str, list[dict[str, Any]]]:
        """Convert merged COMET/arXiv rows into table-shaped upload rows."""
        papers: list[dict[str, Any]] = []
        authors: list[dict[str, Any]] = []
        institutions: dict[str, dict[str, Any]] = {}
        raw_names_by_key: defaultdict[str, set[str]] = defaultdict(set)
        links: list[dict[str, Any]] = []

        for merged in merged_rows:
            arxiv_id = self.normalizer.arxiv_id(str(merged.get("arxiv_id", "")))
            if not arxiv_id:
                raise ValueError("Merged row is missing arxiv_id")

            arxiv_metadata = merged.get("arxiv_metadata") or {}
            category_source = merged.get("categories") or arxiv_metadata.get(
                "categories"
            )
            category_names = self._category_names(category_source)
            primary_category = self._primary_category(category_source, category_names)

            papers.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": self.normalizer.text(merged.get("title"))
                    or f"arXiv {arxiv_id}",
                    "abstract": self.normalizer.text(merged.get("abstract")),
                    "doi": merged.get("doi") or arxiv_metadata.get("doi"),
                    "journal_ref": arxiv_metadata.get("journal-ref")
                    or arxiv_metadata.get("journal_ref"),
                    "primary_category": primary_category,
                    "categories": category_names,
                    "published_at": self._published_at(arxiv_metadata),
                    "updated_at": arxiv_metadata.get("update_date"),
                    "raw_metadata": {
                        "arxiv": arxiv_metadata,
                        "comet": {
                            "doi": merged.get("doi"),
                            "version": merged.get("version"),
                        },
                    },
                }
            )

            for author_position, author in enumerate(
                merged.get("authors") or [], start=1
            ):
                authors.append(
                    {
                        "arxiv_id": arxiv_id,
                        "author_position": author_position,
                        "raw_name": author.get("raw_name") or "",
                        "normalized_name": (
                            author.get("normalized_name")
                            or self.normalizer.author_name(author.get("raw_name") or "")
                        ),
                        "extraction_source": author.get("extraction_source") or "comet",
                        "extraction_confidence": author.get("extraction_confidence"),
                    }
                )

                for affiliation_position, affiliation in enumerate(
                    author.get("affiliations") or [], start=1
                ):
                    institution_key = affiliation.get("institution_key")
                    if not institution_key:
                        institution_key = self.normalizer.institution_key(
                            {
                                "ror_id": affiliation.get("ror_id"),
                                "affiliation": affiliation.get("raw_affiliation"),
                            }
                        )

                    raw_affiliation = affiliation.get("raw_affiliation")
                    normalized_affiliation = affiliation.get("normalized_affiliation")
                    display_name = (
                        normalized_affiliation or raw_affiliation or institution_key
                    )

                    institutions.setdefault(
                        institution_key,
                        {
                            "institution_key": institution_key,
                            "display_name": display_name,
                            "raw_names": [],
                            "ror_id": affiliation.get("ror_id"),
                            "geocode_query": display_name,
                        },
                    )
                    if raw_affiliation:
                        raw_names_by_key[institution_key].add(raw_affiliation)

                    links.append(
                        {
                            "arxiv_id": arxiv_id,
                            "author_position": author_position,
                            "institution_key": institution_key,
                            "raw_affiliation": raw_affiliation,
                            "affiliation_position": affiliation_position,
                            "extraction_source": affiliation.get("extraction_source")
                            or "comet",
                            "extraction_confidence": affiliation.get(
                                "extraction_confidence"
                            ),
                        }
                    )

        for institution_key, raw_names in raw_names_by_key.items():
            institutions[institution_key]["raw_names"] = sorted(raw_names)

        return {
            "papers": papers,
            "authors": authors,
            "institutions": list(institutions.values()),
            "links": links,
        }

    def _upload_papers(self, conn: Connection, rows: Sequence[dict[str, Any]]) -> None:
        if not rows:
            return

        paper_sql = text(
            """
            INSERT INTO arxiv_papers (
              arxiv_id, title, abstract, doi, journal_ref,
              primary_category, categories, published_at, updated_at, raw_metadata
            )
            VALUES (
              :arxiv_id, :title, :abstract, :doi, :journal_ref,
              :primary_category, :categories, :published_at, :updated_at, :raw_metadata
            )
            ON CONFLICT (arxiv_id) DO UPDATE SET
              title = EXCLUDED.title,
              abstract = EXCLUDED.abstract,
              doi = EXCLUDED.doi,
              journal_ref = EXCLUDED.journal_ref,
              primary_category = EXCLUDED.primary_category,
              categories = EXCLUDED.categories,
              published_at = EXCLUDED.published_at,
              updated_at = EXCLUDED.updated_at,
              raw_metadata = EXCLUDED.raw_metadata
            """
        ).bindparams(
            bindparam("categories", type_=ARRAY(Text())),
            bindparam("raw_metadata", type_=JSONB),
        )
        conn.execute(paper_sql, list(rows))

        category_delete_sql = text(
            """
            DELETE FROM arxiv_paper_categories
            WHERE arxiv_id = :arxiv_id
              AND NOT (category = ANY(:categories))
            """
        ).bindparams(bindparam("categories", type_=ARRAY(Text())))
        conn.execute(
            category_delete_sql,
            [
                {"arxiv_id": row["arxiv_id"], "categories": row["categories"]}
                for row in rows
            ],
        )

        category_rows = [
            {
                "arxiv_id": row["arxiv_id"],
                "category": category,
                "is_primary": category == row["primary_category"],
            }
            for row in rows
            for category in row["categories"]
        ]
        if category_rows:
            category_sql = text(
                """
                INSERT INTO arxiv_paper_categories (arxiv_id, category, is_primary)
                VALUES (:arxiv_id, :category, :is_primary)
                ON CONFLICT (arxiv_id, category) DO UPDATE SET
                  is_primary = EXCLUDED.is_primary
                """
            )
            conn.execute(category_sql, category_rows)

    def _upload_authors(self, conn: Connection, rows: Sequence[dict[str, Any]]) -> None:
        if not rows:
            return

        author_sql = text(
            """
            INSERT INTO paper_authors (
              arxiv_id, author_position, raw_name, normalized_name,
              extraction_source, extraction_confidence
            )
            VALUES (
              :arxiv_id, :author_position, :raw_name, :normalized_name,
              :extraction_source, :extraction_confidence
            )
            ON CONFLICT (arxiv_id, author_position) DO UPDATE SET
              raw_name = EXCLUDED.raw_name,
              normalized_name = EXCLUDED.normalized_name,
              extraction_source = EXCLUDED.extraction_source,
              extraction_confidence = EXCLUDED.extraction_confidence
            """
        )
        conn.execute(author_sql, list(rows))

    def _upload_institutions(
        self, conn: Connection, rows: Sequence[dict[str, Any]]
    ) -> None:
        if not rows:
            return

        institution_sql = text(
            """
            INSERT INTO institutions (
              institution_key, display_name, raw_names, ror_id, openalex_id,
              geocode_status, geocode_query, geocode_source, geocode_raw,
              country_code, country, region, city, lat, lon, geocoded_at
            )
            VALUES (
              :institution_key, :display_name, :raw_names, :ror_id, :openalex_id,
              :geocode_status, :geocode_query, :geocode_source, :geocode_raw,
              :country_code, :country, :region, :city, :lat, :lon, :geocoded_at
            )
            ON CONFLICT (institution_key) DO UPDATE SET
              display_name = EXCLUDED.display_name,
              raw_names = (
                SELECT ARRAY(
                  SELECT DISTINCT raw_name
                  FROM unnest(institutions.raw_names || EXCLUDED.raw_names) AS raw_name
                  WHERE raw_name IS NOT NULL
                  ORDER BY raw_name
                )
              ),
              ror_id = COALESCE(institutions.ror_id, EXCLUDED.ror_id),
              openalex_id = COALESCE(institutions.openalex_id, EXCLUDED.openalex_id),
              geocode_status = CASE
                WHEN EXCLUDED.geocode_status <> 'pending'
                  OR institutions.geocode_status = 'pending'
                THEN EXCLUDED.geocode_status
                ELSE institutions.geocode_status
              END,
              geocode_query = COALESCE(institutions.geocode_query, EXCLUDED.geocode_query),
              geocode_source = COALESCE(EXCLUDED.geocode_source, institutions.geocode_source),
              geocode_raw = CASE
                WHEN EXCLUDED.geocode_raw <> '{}'::jsonb THEN EXCLUDED.geocode_raw
                ELSE institutions.geocode_raw
              END,
              country_code = COALESCE(EXCLUDED.country_code, institutions.country_code),
              country = COALESCE(EXCLUDED.country, institutions.country),
              region = COALESCE(EXCLUDED.region, institutions.region),
              city = COALESCE(EXCLUDED.city, institutions.city),
              lat = COALESCE(EXCLUDED.lat, institutions.lat),
              lon = COALESCE(EXCLUDED.lon, institutions.lon),
              geocoded_at = COALESCE(EXCLUDED.geocoded_at, institutions.geocoded_at)
            """
        ).bindparams(
            bindparam("raw_names", type_=ARRAY(Text())),
            bindparam("geocode_raw", type_=JSONB),
        )
        conn.execute(institution_sql, list(rows))

    def _upload_links(self, conn: Connection, rows: Sequence[dict[str, Any]]) -> None:
        if not rows:
            return

        natural_key_rows = [
            row
            for row in rows
            if row.get("paper_author_id") is None or row.get("institution_id") is None
        ]
        id_rows = [
            row
            for row in rows
            if row.get("paper_author_id") is not None
            and row.get("institution_id") is not None
        ]

        if natural_key_rows:
            link_by_keys_sql = text(
                """
                INSERT INTO paper_author_institutions (
                  paper_author_id, institution_id, raw_affiliation,
                  affiliation_position, extraction_source, extraction_confidence
                )
                SELECT
                  pa.id,
                  i.id,
                  :raw_affiliation,
                  :affiliation_position,
                  :extraction_source,
                  :extraction_confidence
                FROM paper_authors pa
                JOIN institutions i
                  ON i.institution_key = :institution_key
                WHERE pa.arxiv_id = :arxiv_id
                  AND pa.author_position = :author_position
                ON CONFLICT (paper_author_id, institution_id) DO UPDATE SET
                  raw_affiliation = COALESCE(
                    paper_author_institutions.raw_affiliation,
                    EXCLUDED.raw_affiliation
                  ),
                  affiliation_position = COALESCE(
                    paper_author_institutions.affiliation_position,
                    EXCLUDED.affiliation_position
                  ),
                  extraction_source = EXCLUDED.extraction_source,
                  extraction_confidence = EXCLUDED.extraction_confidence
                """
            )
            conn.execute(link_by_keys_sql, natural_key_rows)

        if id_rows:
            link_by_ids_sql = text(
                """
                INSERT INTO paper_author_institutions (
                  paper_author_id, institution_id, raw_affiliation,
                  affiliation_position, extraction_source, extraction_confidence
                )
                VALUES (
                  :paper_author_id, :institution_id, :raw_affiliation,
                  :affiliation_position, :extraction_source, :extraction_confidence
                )
                ON CONFLICT (paper_author_id, institution_id) DO UPDATE SET
                  raw_affiliation = COALESCE(
                    paper_author_institutions.raw_affiliation,
                    EXCLUDED.raw_affiliation
                  ),
                  affiliation_position = COALESCE(
                    paper_author_institutions.affiliation_position,
                    EXCLUDED.affiliation_position
                  ),
                  extraction_source = EXCLUDED.extraction_source,
                  extraction_confidence = EXCLUDED.extraction_confidence
                """
            )
            conn.execute(link_by_ids_sql, id_rows)

    def _paper_row(self, row: DatabaseRow) -> dict[str, Any]:
        arxiv_metadata = (
            row.get("arxiv_metadata") or row.get("raw_metadata", {}).get("arxiv") or {}
        )
        arxiv_id = self.normalizer.arxiv_id(str(row.get("arxiv_id", "")))
        if not arxiv_id:
            raise ValueError("Paper row is missing arxiv_id")

        category_names = self._category_names(
            row.get("categories") or arxiv_metadata.get("categories")
        )
        primary_category = row.get("primary_category") or self._primary_category(
            row.get("categories"), category_names
        )

        return {
            "arxiv_id": arxiv_id,
            "title": self.normalizer.text(row.get("title")) or f"arXiv {arxiv_id}",
            "abstract": self.normalizer.text(row.get("abstract")),
            "doi": row.get("doi") or arxiv_metadata.get("doi"),
            "journal_ref": (
                row.get("journal_ref")
                or arxiv_metadata.get("journal-ref")
                or arxiv_metadata.get("journal_ref")
            ),
            "primary_category": primary_category,
            "categories": category_names,
            "published_at": row.get("published_at")
            or self._published_at(arxiv_metadata),
            "updated_at": row.get("updated_at") or arxiv_metadata.get("update_date"),
            "raw_metadata": row.get("raw_metadata") or {"arxiv": arxiv_metadata},
        }

    def _author_row(self, row: DatabaseRow) -> dict[str, Any]:
        arxiv_id = self.normalizer.arxiv_id(str(row.get("arxiv_id", "")))
        if not arxiv_id:
            raise ValueError("Author row is missing arxiv_id")

        raw_name = row.get("raw_name") or ""
        return {
            "arxiv_id": arxiv_id,
            "author_position": self._required_int(row, "author_position"),
            "raw_name": raw_name,
            "normalized_name": row.get("normalized_name")
            or self.normalizer.author_name(raw_name),
            "extraction_source": row.get("extraction_source"),
            "extraction_confidence": row.get("extraction_confidence"),
        }

    def _institution_row(self, row: DatabaseRow) -> dict[str, Any]:
        institution_key = row.get("institution_key")
        if not institution_key:
            raise ValueError("Institution row is missing institution_key")

        raw_names = self._dedupe_texts(row.get("raw_names") or [])
        display_name = self.normalizer.text(row.get("display_name")) or (
            raw_names[0] if raw_names else institution_key
        )
        geocode_status = row.get("geocode_status") or "pending"
        valid_statuses = {"pending", "resolved", "failed", "ambiguous", "skip"}
        if geocode_status not in valid_statuses:
            raise ValueError(
                f"Invalid geocode_status for {institution_key}: {geocode_status}"
            )

        lat = row.get("lat")
        lon = row.get("lon")
        if (lat is None) != (lon is None):
            raise ValueError(
                f"Institution {institution_key} must provide both lat and lon, or neither"
            )

        return {
            "institution_key": institution_key,
            "display_name": display_name,
            "raw_names": raw_names,
            "ror_id": row.get("ror_id"),
            "openalex_id": row.get("openalex_id"),
            "geocode_status": geocode_status,
            "geocode_query": row.get("geocode_query") or display_name,
            "geocode_source": row.get("geocode_source"),
            "geocode_raw": row.get("geocode_raw") or {},
            "country_code": row.get("country_code"),
            "country": row.get("country"),
            "region": row.get("region"),
            "city": row.get("city"),
            "lat": lat,
            "lon": lon,
            "geocoded_at": row.get("geocoded_at"),
        }

    def _link_row(self, row: DatabaseRow) -> dict[str, Any]:
        if (
            row.get("paper_author_id") is not None
            and row.get("institution_id") is not None
        ):
            return {
                "paper_author_id": row.get("paper_author_id"),
                "institution_id": row.get("institution_id"),
                "raw_affiliation": row.get("raw_affiliation"),
                "affiliation_position": row.get("affiliation_position"),
                "extraction_source": row.get("extraction_source"),
                "extraction_confidence": row.get("extraction_confidence"),
                "arxiv_id": None,
                "author_position": None,
                "institution_key": None,
            }

        arxiv_id = self.normalizer.arxiv_id(str(row.get("arxiv_id", "")))
        if not arxiv_id:
            raise ValueError("Link row is missing arxiv_id")
        if not row.get("institution_key"):
            raise ValueError("Link row is missing institution_key")

        return {
            "paper_author_id": None,
            "institution_id": None,
            "arxiv_id": arxiv_id,
            "author_position": self._required_int(row, "author_position"),
            "institution_key": row.get("institution_key"),
            "raw_affiliation": row.get("raw_affiliation"),
            "affiliation_position": row.get("affiliation_position"),
            "extraction_source": row.get("extraction_source"),
            "extraction_confidence": row.get("extraction_confidence"),
        }

    def _category_names(self, categories: Any) -> list[str]:
        if not categories:
            return []
        if isinstance(categories, str):
            return self._dedupe_texts(categories.split())

        names: list[str] = []
        for category in categories:
            if isinstance(category, str):
                names.append(category)
            elif isinstance(category, Mapping):
                name = category.get("name") or category.get("category")
                if name:
                    names.append(str(name))
            else:
                names.append(str(category))
        return self._dedupe_texts(names)

    def _primary_category(
        self, categories: Any, category_names: Sequence[str]
    ) -> str | None:
        if categories and not isinstance(categories, str):
            for category in categories:
                if isinstance(category, Mapping) and category.get("is_primary"):
                    name = category.get("name") or category.get("category")
                    return str(name) if name else None
        return category_names[0] if category_names else None

    def _published_at(self, arxiv_metadata: DatabaseRow) -> Any:
        versions = arxiv_metadata.get("versions") or []
        if not versions:
            return None
        first_version = versions[0] or {}
        return first_version.get("created")

    def _dedupe_texts(self, values: Iterable[Any]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            text_value = self.normalizer.text(value)
            if text_value and text_value not in seen:
                seen.add(text_value)
                deduped.append(text_value)
        return deduped

    def _required_int(self, row: DatabaseRow, field: str) -> int:
        value = row.get(field)
        if value is None:
            raise ValueError(f"Row is missing {field}")
        return int(value)
