BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS arxiv_papers (
  arxiv_id TEXT PRIMARY KEY,

  title TEXT NOT NULL,
  abstract TEXT,
  doi TEXT,
  journal_ref TEXT,

  primary_category TEXT,
  categories TEXT[] NOT NULL DEFAULT '{}',

  published_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,

  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arxiv_paper_categories (
  arxiv_id TEXT NOT NULL REFERENCES arxiv_papers(arxiv_id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  is_primary BOOLEAN NOT NULL DEFAULT false,

  PRIMARY KEY (arxiv_id, category)
);

CREATE TABLE IF NOT EXISTS paper_authors (
  id BIGSERIAL PRIMARY KEY,

  arxiv_id TEXT NOT NULL REFERENCES arxiv_papers(arxiv_id) ON DELETE CASCADE,
  author_position INTEGER NOT NULL,

  raw_name TEXT NOT NULL,
  normalized_name TEXT,

  extraction_source TEXT,
  extraction_confidence NUMERIC(4, 3),

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (arxiv_id, author_position)
);

CREATE TABLE IF NOT EXISTS institutions (
  id BIGSERIAL PRIMARY KEY,

  institution_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,

  raw_names TEXT[] NOT NULL DEFAULT '{}',

  ror_id TEXT,
  openalex_id TEXT,

  geocode_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (geocode_status IN ('pending', 'resolved', 'failed', 'ambiguous', 'skip')),

  geocode_query TEXT,
  geocode_source TEXT,
  geocode_raw JSONB NOT NULL DEFAULT '{}'::jsonb,

  country_code TEXT,
  country TEXT,
  region TEXT,
  city TEXT,

  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,

  geom GEOMETRY(Point, 4326)
    GENERATED ALWAYS AS (
      CASE
        WHEN lat IS NOT NULL AND lon IS NOT NULL
        THEN ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        ELSE NULL
      END
    ) STORED,

  geocoded_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK (lat IS NULL OR (lat >= -90 AND lat <= 90)),
  CHECK (lon IS NULL OR (lon >= -180 AND lon <= 180)),
  CHECK (
    (lat IS NULL AND lon IS NULL)
    OR
    (lat IS NOT NULL AND lon IS NOT NULL)
  )
);

DROP TRIGGER IF EXISTS institutions_touch_updated_at ON institutions;

CREATE TRIGGER institutions_touch_updated_at
BEFORE UPDATE ON institutions
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

CREATE TABLE IF NOT EXISTS paper_author_institutions (
  id BIGSERIAL PRIMARY KEY,

  paper_author_id BIGINT NOT NULL REFERENCES paper_authors(id) ON DELETE CASCADE,
  institution_id BIGINT NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,

  raw_affiliation TEXT,
  affiliation_position INTEGER,

  extraction_source TEXT,
  extraction_confidence NUMERIC(4, 3),

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (paper_author_id, institution_id)
);

CREATE INDEX IF NOT EXISTS idx_arxiv_papers_primary_category
  ON arxiv_papers(primary_category);

CREATE INDEX IF NOT EXISTS idx_arxiv_papers_categories_gin
  ON arxiv_papers
  USING GIN (categories);

CREATE INDEX IF NOT EXISTS idx_arxiv_paper_categories_category
  ON arxiv_paper_categories(category);

CREATE INDEX IF NOT EXISTS idx_paper_authors_arxiv_id
  ON paper_authors(arxiv_id);

CREATE INDEX IF NOT EXISTS idx_paper_author_institutions_author_id
  ON paper_author_institutions(paper_author_id);

CREATE INDEX IF NOT EXISTS idx_paper_author_institutions_institution_id
  ON paper_author_institutions(institution_id);

CREATE INDEX IF NOT EXISTS idx_institutions_geocode_status
  ON institutions(geocode_status);

CREATE INDEX IF NOT EXISTS idx_institutions_country_code
  ON institutions(country_code);

CREATE INDEX IF NOT EXISTS idx_institutions_geom
  ON institutions
  USING GIST (geom)
  WHERE geom IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_institutions_lat_lon
  ON institutions(lat, lon)
  WHERE lat IS NOT NULL AND lon IS NOT NULL;

COMMIT;