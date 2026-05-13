BEGIN;

CREATE OR REPLACE VIEW core_arxiv_table AS
SELECT
  p.arxiv_id,
  p.title,
  p.abstract,
  p.doi,
  p.journal_ref,
  p.primary_category,
  p.categories,
  p.published_at,
  p.updated_at,
  p.raw_metadata,

  COALESCE(
    (
      SELECT jsonb_agg(
        jsonb_build_object(
          'author_id', a.id,
          'position', a.author_position,
          'raw_name', a.raw_name,
          'normalized_name', a.normalized_name,
          'institutions', COALESCE(
            (
              SELECT jsonb_agg(
                jsonb_build_object(
                  'institution_id', i.id,
                  'institution_key', i.institution_key,
                  'display_name', i.display_name,
                  'raw_affiliation', pai.raw_affiliation,
                  'city', i.city,
                  'region', i.region,
                  'country', i.country,
                  'country_code', i.country_code,
                  'lat', i.lat,
                  'lon', i.lon,
                  'geometry', CASE
                    WHEN i.geom IS NOT NULL
                    THEN ST_AsGeoJSON(i.geom)::jsonb
                    ELSE NULL
                  END,
                  'geocode_status', i.geocode_status
                )
                ORDER BY pai.affiliation_position NULLS LAST, i.display_name
              )
              FROM paper_author_institutions pai
              JOIN institutions i
                ON i.id = pai.institution_id
              WHERE pai.paper_author_id = a.id
            ),
            '[]'::jsonb
          )
        )
        ORDER BY a.author_position
      )
      FROM paper_authors a
      WHERE a.arxiv_id = p.arxiv_id
    ),
    '[]'::jsonb
  ) AS authors

FROM arxiv_papers p;

DROP MATERIALIZED VIEW IF EXISTS arxiv_network_edges_by_category;
DROP MATERIALIZED VIEW IF EXISTS arxiv_network_nodes_by_category;

CREATE MATERIALIZED VIEW arxiv_network_nodes_by_category AS
WITH paper_category_rows AS (
  SELECT arxiv_id, category
  FROM arxiv_paper_categories

  UNION ALL

  SELECT arxiv_id, '__all__' AS category
  FROM arxiv_papers
),

paper_institutions AS (
  SELECT DISTINCT
    pcr.category,
    pcr.arxiv_id,
    pai.institution_id
  FROM paper_category_rows pcr
  JOIN paper_authors pa
    ON pa.arxiv_id = pcr.arxiv_id
  JOIN paper_author_institutions pai
    ON pai.paper_author_id = pa.id
  JOIN institutions i
    ON i.id = pai.institution_id
  WHERE i.geocode_status = 'resolved'
    AND i.geom IS NOT NULL
)

SELECT
  pi.category,

  i.id AS institution_id,
  i.institution_key,
  i.display_name,

  i.city,
  i.region,
  i.country,
  i.country_code,

  i.lat,
  i.lon,
  i.geom,
  ST_AsGeoJSON(i.geom)::jsonb AS geometry,

  COUNT(DISTINCT pi.arxiv_id)::INTEGER AS paper_count

FROM paper_institutions pi
JOIN institutions i
  ON i.id = pi.institution_id
GROUP BY
  pi.category,
  i.id,
  i.institution_key,
  i.display_name,
  i.city,
  i.region,
  i.country,
  i.country_code,
  i.lat,
  i.lon,
  i.geom;

CREATE UNIQUE INDEX idx_arxiv_network_nodes_by_category_unique
  ON arxiv_network_nodes_by_category(category, institution_id);

CREATE INDEX idx_arxiv_network_nodes_by_category_category
  ON arxiv_network_nodes_by_category(category);

CREATE INDEX idx_arxiv_network_nodes_by_category_geom
  ON arxiv_network_nodes_by_category
  USING GIST (geom);

CREATE INDEX idx_arxiv_network_nodes_by_category_paper_count
  ON arxiv_network_nodes_by_category(category, paper_count DESC);

CREATE MATERIALIZED VIEW arxiv_network_edges_by_category AS
WITH paper_category_rows AS (
  SELECT arxiv_id, category
  FROM arxiv_paper_categories

  UNION ALL

  SELECT arxiv_id, '__all__' AS category
  FROM arxiv_papers
),

paper_institutions AS (
  SELECT DISTINCT
    pcr.category,
    pcr.arxiv_id,
    p.published_at,
    pai.institution_id
  FROM paper_category_rows pcr
  JOIN arxiv_papers p
    ON p.arxiv_id = pcr.arxiv_id
  JOIN paper_authors pa
    ON pa.arxiv_id = pcr.arxiv_id
  JOIN paper_author_institutions pai
    ON pai.paper_author_id = pa.id
  JOIN institutions i
    ON i.id = pai.institution_id
  WHERE i.geocode_status = 'resolved'
    AND i.geom IS NOT NULL
),

institution_pairs AS (
  SELECT
    pi1.category,
    pi1.arxiv_id,
    pi1.published_at,

    pi1.institution_id AS source_institution_id,
    pi2.institution_id AS target_institution_id

  FROM paper_institutions pi1
  JOIN paper_institutions pi2
    ON pi1.category = pi2.category
   AND pi1.arxiv_id = pi2.arxiv_id
   AND pi1.institution_id < pi2.institution_id
)

SELECT
  ip.category,

  ip.source_institution_id,
  source_i.display_name AS source_name,
  source_i.city AS source_city,
  source_i.region AS source_region,
  source_i.country AS source_country,
  source_i.country_code AS source_country_code,
  source_i.lat AS source_lat,
  source_i.lon AS source_lon,

  ip.target_institution_id,
  target_i.display_name AS target_name,
  target_i.city AS target_city,
  target_i.region AS target_region,
  target_i.country AS target_country,
  target_i.country_code AS target_country_code,
  target_i.lat AS target_lat,
  target_i.lon AS target_lon,

  ST_MakeLine(source_i.geom, target_i.geom) AS geom,
  ST_AsGeoJSON(ST_MakeLine(source_i.geom, target_i.geom))::jsonb AS geometry,

  COUNT(DISTINCT ip.arxiv_id)::INTEGER AS edge_weight,
  MIN(ip.published_at) AS first_paper_at,
  MAX(ip.published_at) AS latest_paper_at,

  ARRAY_AGG(DISTINCT ip.arxiv_id ORDER BY ip.arxiv_id) AS sample_arxiv_ids

FROM institution_pairs ip
JOIN institutions source_i
  ON source_i.id = ip.source_institution_id
JOIN institutions target_i
  ON target_i.id = ip.target_institution_id
GROUP BY
  ip.category,

  ip.source_institution_id,
  source_i.display_name,
  source_i.city,
  source_i.region,
  source_i.country,
  source_i.country_code,
  source_i.lat,
  source_i.lon,
  source_i.geom,

  ip.target_institution_id,
  target_i.display_name,
  target_i.city,
  target_i.region,
  target_i.country,
  target_i.country_code,
  target_i.lat,
  target_i.lon,
  target_i.geom;

CREATE UNIQUE INDEX idx_arxiv_network_edges_by_category_unique
  ON arxiv_network_edges_by_category(
    category,
    source_institution_id,
    target_institution_id
  );

CREATE INDEX idx_arxiv_network_edges_by_category_category
  ON arxiv_network_edges_by_category(category);

CREATE INDEX idx_arxiv_network_edges_by_category_weight
  ON arxiv_network_edges_by_category(category, edge_weight DESC);

CREATE INDEX idx_arxiv_network_edges_by_category_geom
  ON arxiv_network_edges_by_category
  USING GIST (geom);

COMMIT;