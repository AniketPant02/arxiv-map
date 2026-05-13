BEGIN;

CREATE OR REPLACE FUNCTION refresh_arxiv_network()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW arxiv_network_nodes_by_category;
  REFRESH MATERIALIZED VIEW arxiv_network_edges_by_category;
END;
$$;

CREATE OR REPLACE FUNCTION refresh_arxiv_network_concurrently()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY arxiv_network_nodes_by_category;
  REFRESH MATERIALIZED VIEW CONCURRENTLY arxiv_network_edges_by_category;
END;
$$;

COMMIT;