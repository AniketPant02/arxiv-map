from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .normalize import Normalizer


class ArxivMetadataWarehouse:
    """Using DuckDB for arxiv querying."""

    def __init__(
        self,
        source_path: str | Path = "data/raw/arxiv-metadata-oai-snapshot.json",
        cache_path: str | Path = "data/processed/arxiv.duckdb",
    ) -> None:
        self.source_path = Path(source_path)
        self.cache_path = Path(cache_path)
        self.normalizer = Normalizer()

    def build(self, rebuild: bool = False) -> None:
        """Create the DuckDB cache from the source JSONL file if needed."""
        self._ensure_source_exists()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        if rebuild and self.cache_path.exists():
            self.cache_path.unlink()

        with self._connect() as conn:
            if not rebuild and self._has_tables(
                conn, "arxiv_papers", "arxiv_paper_categories"
            ):
                return

            conn.execute("DROP TABLE IF EXISTS arxiv_paper_categories")
            conn.execute("DROP TABLE IF EXISTS arxiv_papers")
            conn.execute(
                """
                CREATE TABLE arxiv_papers AS
                SELECT
                  regexp_replace(
                    regexp_replace(id, '^arXiv:', ''),
                    'v[0-9]+$',
                    ''
                  ) AS arxiv_id,
                  regexp_replace(trim(title), '\\s+', ' ', 'g') AS title,
                  trim(abstract) AS abstract,
                  doi,
                  "journal-ref" AS journal_ref,
                  coalesce(categories, '') AS categories_text,
                  nullif(split_part(coalesce(categories, ''), ' ', 1), '')
                    AS primary_category,
                  try_strptime(
                    versions[1].created,
                    '%a, %-d %b %Y %H:%M:%S GMT'
                  ) AS published_at,
                  update_date AS updated_at,
                  versions[1].created AS first_version_created
                FROM read_json_auto(?, records = true)
                """,
                [str(self.source_path)],
            )
            conn.execute(
                """
                CREATE TABLE arxiv_paper_categories AS
                SELECT
                  p.arxiv_id,
                  category,
                  category_index = 1 AS is_primary,
                  p.published_at
                FROM arxiv_papers p,
                  unnest(string_split(p.categories_text, ' '))
                    WITH ORDINALITY AS category_rows(category, category_index)
                WHERE category IS NOT NULL
                  AND category <> ''
                """
            )
            self._create_index(
                conn, "idx_arxiv_papers_arxiv_id", "arxiv_papers", "arxiv_id"
            )
            self._create_index(
                conn,
                "idx_arxiv_papers_published_at",
                "arxiv_papers",
                "published_at",
            )
            self._create_index(
                conn,
                "idx_arxiv_paper_categories_category",
                "arxiv_paper_categories",
                "category",
            )
            self._create_index(
                conn,
                "idx_arxiv_paper_categories_published_at",
                "arxiv_paper_categories",
                "published_at",
            )

    def find_by_ids(self, arxiv_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return merger-compatible arXiv metadata rows keyed by normalized ID."""
        clean_ids = self._normalized_ids(arxiv_ids)
        if not clean_ids:
            return {}

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  arxiv_id,
                  title,
                  abstract,
                  doi,
                  journal_ref,
                  categories_text,
                  updated_at,
                  first_version_created
                FROM arxiv_papers
                WHERE arxiv_id IN (SELECT unnest(?))
                """,
                [clean_ids],
            ).fetchall()

        rows_by_id: dict[str, dict[str, Any]] = {}
        for (
            arxiv_id,
            title,
            abstract,
            doi,
            journal_ref,
            categories_text,
            updated_at,
            first_version_created,
        ) in rows:
            rows_by_id[arxiv_id] = {
                "id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "doi": doi,
                "journal-ref": journal_ref,
                "categories": categories_text or "",
                "update_date": self._string_or_none(updated_at),
                "versions": [
                    {"version": "v1", "created": first_version_created}
                ]
                if first_version_created
                else [],
            }
        return rows_by_id

    def query(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        """Run caller-owned SQL against the warehouse and return a DataFrame."""
        with self._connect() as conn:
            if params is None:
                return conn.execute(sql).fetchdf()
            return conn.execute(sql, params).fetchdf()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.cache_path))

    def _ensure_source_exists(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {self.source_path}")

    def _normalized_ids(self, arxiv_ids: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        clean_ids: list[str] = []
        for raw_id in arxiv_ids:
            clean_id = self.normalizer.arxiv_id(str(raw_id))
            if clean_id and clean_id not in seen:
                seen.add(clean_id)
                clean_ids.append(clean_id)
        return clean_ids

    @staticmethod
    def _has_tables(conn: duckdb.DuckDBPyConnection, *table_names: str) -> bool:
        existing = {
            row[0]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }
        return set(table_names).issubset(existing)

    @staticmethod
    def _create_index(
        conn: duckdb.DuckDBPyConnection,
        index_name: str,
        table_name: str,
        column_name: str,
    ) -> None:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        return None if value is None else str(value)


class CometWarehouse:
    """Fast local query cache for COMET affiliation extraction JSON-lines output."""

    def __init__(
        self,
        source_path: str | Path = "data/raw/comet_data_orig.jsonl",
        cache_path: str | Path = "data/processed/comet.duckdb",
    ) -> None:
        self.source_path = Path(source_path)
        self.cache_path = Path(cache_path)
        self.normalizer = Normalizer()

    def build(
        self, rebuild: bool = False, include_affiliations: bool = False
    ) -> None:
        """Create the DuckDB cache from the source JSONL file if needed.

        The exploded affiliation table is useful for affiliation-level EDA, but
        it is much more expensive to build than the paper lookup table. Keep it
        opt-in so the default path stays fast for merge/enrichment workflows.
        """
        self._ensure_source_exists()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        if rebuild and self.cache_path.exists():
            self.cache_path.unlink()

        with self._connect() as conn:
            required_tables = ["comet_papers"]
            if include_affiliations:
                required_tables.append("comet_affiliations")

            if not rebuild and self._has_tables(conn, *required_tables):
                return

            if rebuild or not self._has_tables(conn, "comet_papers"):
                conn.execute("DROP TABLE IF EXISTS comet_papers")
                self._build_papers(conn)

            if include_affiliations and (
                rebuild or not self._has_tables(conn, "comet_affiliations")
            ):
                conn.execute("DROP TABLE IF EXISTS comet_affiliations")
                self._build_affiliations(conn)

    def find_by_ids(self, arxiv_ids: Iterable[str]) -> list[dict[str, Any]]:
        """Return COMET rows compatible with CometArxivMerger."""
        clean_ids = self._normalized_ids(arxiv_ids)
        if not clean_ids:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT arxiv_id, doi, version, prediction_json
                FROM comet_papers
                WHERE arxiv_id IN (SELECT unnest(?))
                ORDER BY arxiv_id
                """,
                [clean_ids],
            ).fetchall()
        return [self._comet_row(row) for row in rows]

    def iter_rows(self, limit: int | None = None) -> Iterator[dict[str, Any]]:
        """Yield COMET rows in merger-compatible shape."""
        sql = """
            SELECT arxiv_id, doi, version, prediction_json
            FROM comet_papers
            ORDER BY arxiv_id
        """
        params: list[Any] | None = None
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be non-negative")
            sql += " LIMIT ?"
            params = [limit]

        with self._connect() as conn:
            if params is None:
                rows = conn.execute(sql).fetchall()
            else:
                rows = conn.execute(sql, params).fetchall()

        for row in rows:
            yield self._comet_row(row)

    def query(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        """Run caller-owned SQL against the warehouse and return a DataFrame."""
        with self._connect() as conn:
            if params is None:
                return conn.execute(sql).fetchdf()
            return conn.execute(sql, params).fetchdf()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.cache_path))

    def _build_papers(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            CREATE TABLE comet_papers AS
            SELECT
              regexp_replace(
                regexp_replace(arxiv_id, '^arXiv:', ''),
                'v[0-9]+$',
                ''
              ) AS arxiv_id,
              doi,
              version,
              to_json(prediction) AS prediction_json
            FROM read_json_auto(?, records = true)
            """,
            [str(self.source_path)],
        )
        self._create_index(
            conn, "idx_comet_papers_arxiv_id", "comet_papers", "arxiv_id"
        )

    def _build_affiliations(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            CREATE TABLE comet_affiliations AS
            SELECT
              regexp_replace(
                regexp_replace(p.arxiv_id, '^arXiv:', ''),
                'v[0-9]+$',
                ''
              ) AS arxiv_id,
              author_rows.author_index AS author_position,
              author_rows.author.name AS raw_name,
              affiliation_rows.affiliation_index AS affiliation_position,
              affiliation_rows.affiliation.affiliation AS raw_affiliation,
              affiliation_rows.affiliation.ror_id AS ror_id
            FROM read_json_auto(?, records = true) p,
              unnest(p.prediction)
                WITH ORDINALITY AS author_rows(author, author_index),
              unnest(author_rows.author.affiliations)
                WITH ORDINALITY AS affiliation_rows(affiliation, affiliation_index)
            """,
            [str(self.source_path)],
        )
        self._create_index(
            conn, "idx_comet_affiliations_arxiv_id", "comet_affiliations", "arxiv_id"
        )
        self._create_index(
            conn, "idx_comet_affiliations_ror_id", "comet_affiliations", "ror_id"
        )

    def _ensure_source_exists(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {self.source_path}")

    def _normalized_ids(self, arxiv_ids: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        clean_ids: list[str] = []
        for raw_id in arxiv_ids:
            clean_id = self.normalizer.arxiv_id(str(raw_id))
            if clean_id and clean_id not in seen:
                seen.add(clean_id)
                clean_ids.append(clean_id)
        return clean_ids

    @staticmethod
    def _has_tables(conn: duckdb.DuckDBPyConnection, *table_names: str) -> bool:
        existing = {
            row[0]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }
        return set(table_names).issubset(existing)

    @staticmethod
    def _create_index(
        conn: duckdb.DuckDBPyConnection,
        index_name: str,
        table_name: str,
        column_name: str,
    ) -> None:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    @staticmethod
    def _comet_row(row: tuple[Any, ...]) -> dict[str, Any]:
        arxiv_id, doi, version, prediction_json = row
        return {
            "arxiv_id": arxiv_id,
            "doi": doi,
            "version": version,
            "prediction": json.loads(prediction_json or "[]"),
        }


class RorWarehouse:
    """Fast local query cache for ROR organization metadata."""

    def __init__(
        self,
        source_path: str | Path = "data/processed/v2.7-2026-05-12-ror-data.json",
        cache_path: str | Path = "data/processed/ror.duckdb",
    ) -> None:
        self.source_path = Path(source_path)
        self.cache_path = Path(cache_path)

    def build(self, rebuild: bool = False) -> None:
        """Create the DuckDB cache from the ROR JSON file if needed."""
        self._ensure_source_exists()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        if rebuild and self.cache_path.exists():
            self.cache_path.unlink()

        with self._connect() as conn:
            if not rebuild and self._has_tables(
                conn, "ror_institutions", "ror_names"
            ):
                return

            conn.execute("DROP TABLE IF EXISTS ror_names")
            conn.execute("DROP TABLE IF EXISTS ror_institutions")
            self._build_institutions(conn)
            self._build_names(conn)

    def find_by_ids(self, ror_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return ROR institution rows keyed by bare ROR ID."""
        clean_ids = self._normalized_ror_ids(ror_ids)
        if not clean_ids:
            return {}

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  ror_id,
                  ror_url,
                  display_name,
                  status,
                  organization_types,
                  established,
                  country_code,
                  country,
                  region,
                  city,
                  lat,
                  lon,
                  geonames_id,
                  updated_at
                FROM ror_institutions
                WHERE ror_id IN (SELECT unnest(?))
                """,
                [clean_ids],
            ).fetchall()

        return {
            row[0]: {
                "ror_id": row[0],
                "ror_url": row[1],
                "display_name": row[2],
                "status": row[3],
                "organization_types": json.loads(row[4] or "[]"),
                "established": row[5],
                "country_code": row[6],
                "country": row[7],
                "region": row[8],
                "city": row[9],
                "lat": row[10],
                "lon": row[11],
                "geonames_id": row[12],
                "updated_at": self._string_or_none(row[13]),
            }
            for row in rows
        }

    def search_names(self, name: str, limit: int = 20) -> pd.DataFrame:
        """Search normalized ROR names for exact matches first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        normalized_name = self._normalize_name(name)
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                  n.ror_id,
                  i.ror_url,
                  i.display_name,
                  n.name,
                  n.name_types,
                  n.lang,
                  i.country_code,
                  i.country,
                  i.region,
                  i.city,
                  i.lat,
                  i.lon
                FROM ror_names n
                JOIN ror_institutions i
                  ON i.ror_id = n.ror_id
                WHERE n.normalized_name = ?
                ORDER BY
                  n.is_ror_display DESC,
                  n.is_label DESC,
                  n.is_alias DESC,
                  i.status = 'active' DESC,
                  i.display_name
                LIMIT ?
                """,
                [normalized_name, limit],
            ).fetchdf()

    def query(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        """Run caller-owned SQL against the warehouse and return a DataFrame."""
        with self._connect() as conn:
            if params is None:
                return conn.execute(sql).fetchdf()
            return conn.execute(sql, params).fetchdf()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.cache_path))

    def _build_institutions(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            CREATE TABLE ror_institutions AS
            SELECT
              regexp_extract(id, '([^/]+)$', 1) AS ror_id,
              id AS ror_url,
              coalesce(
                (
                  SELECT name.value
                  FROM unnest(names) AS name_rows(name)
                  WHERE list_contains(name.types, 'ror_display')
                  LIMIT 1
                ),
                names[1].value
              ) AS display_name,
              status,
              to_json(types) AS organization_types,
              established,
              locations[1].geonames_details.country_code AS country_code,
              locations[1].geonames_details.country_name AS country,
              locations[1].geonames_details.country_subdivision_name AS region,
              locations[1].geonames_details.name AS city,
              locations[1].geonames_details.lat AS lat,
              locations[1].geonames_details.lng AS lon,
              locations[1].geonames_id AS geonames_id,
              admin.last_modified.date AS updated_at
            FROM read_json_auto(?, records = true)
            """,
            [str(self.source_path)],
        )
        self._create_index(
            conn, "idx_ror_institutions_ror_id", "ror_institutions", "ror_id"
        )
        self._create_index(
            conn,
            "idx_ror_institutions_country_code",
            "ror_institutions",
            "country_code",
        )

    def _build_names(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            CREATE TABLE ror_names AS
            SELECT
              regexp_extract(r.id, '([^/]+)$', 1) AS ror_id,
              name.value AS name,
              regexp_replace(lower(trim(name.value)), '\\s+', ' ', 'g')
                AS normalized_name,
              to_json(name.types) AS name_types,
              name.lang AS lang,
              list_contains(name.types, 'ror_display') AS is_ror_display,
              list_contains(name.types, 'label') AS is_label,
              list_contains(name.types, 'alias') AS is_alias,
              list_contains(name.types, 'acronym') AS is_acronym
            FROM read_json_auto(?, records = true) r,
              unnest(r.names) AS name_rows(name)
            WHERE name.value IS NOT NULL
              AND trim(name.value) <> ''
            """,
            [str(self.source_path)],
        )
        self._create_index(conn, "idx_ror_names_ror_id", "ror_names", "ror_id")
        self._create_index(
            conn, "idx_ror_names_normalized_name", "ror_names", "normalized_name"
        )

    def _ensure_source_exists(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {self.source_path}")

    @staticmethod
    def _normalized_ror_ids(ror_ids: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        clean_ids: list[str] = []
        for raw_id in ror_ids:
            clean_id = str(raw_id).strip().removeprefix("ror:")
            clean_id = clean_id.rstrip("/").split("/")[-1]
            if clean_id and clean_id not in seen:
                seen.add(clean_id)
                clean_ids.append(clean_id)
        return clean_ids

    @staticmethod
    def _normalize_name(name: str) -> str:
        return " ".join(str(name).lower().strip().split())

    @staticmethod
    def _has_tables(conn: duckdb.DuckDBPyConnection, *table_names: str) -> bool:
        existing = {
            row[0]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }
        return set(table_names).issubset(existing)

    @staticmethod
    def _create_index(
        conn: duckdb.DuckDBPyConnection,
        index_name: str,
        table_name: str,
        column_name: str,
    ) -> None:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        return None if value is None else str(value)
