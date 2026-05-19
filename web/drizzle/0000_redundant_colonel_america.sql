-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TABLE "spatial_ref_sys" (
	"srid" integer PRIMARY KEY NOT NULL,
	"auth_name" varchar(256),
	"auth_srid" integer,
	"srtext" varchar(2048),
	"proj4text" varchar(2048),
	CONSTRAINT "spatial_ref_sys_srid_check" CHECK ((srid > 0) AND (srid <= 998999))
);
--> statement-breakpoint
CREATE TABLE "schema_migrations" (
	"version" text PRIMARY KEY NOT NULL,
	"filename" text NOT NULL,
	"applied_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "arxiv_papers" (
	"arxiv_id" text PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"abstract" text,
	"doi" text,
	"journal_ref" text,
	"primary_category" text,
	"categories" text[] DEFAULT '{""}' NOT NULL,
	"published_at" timestamp with time zone,
	"updated_at" timestamp with time zone,
	"raw_metadata" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "paper_authors" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"arxiv_id" text NOT NULL,
	"author_position" integer NOT NULL,
	"raw_name" text NOT NULL,
	"normalized_name" text,
	"extraction_source" text,
	"extraction_confidence" numeric(4, 3),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "paper_authors_arxiv_id_author_position_key" UNIQUE("arxiv_id","author_position")
);
--> statement-breakpoint
CREATE TABLE "institutions" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"institution_key" text NOT NULL,
	"display_name" text NOT NULL,
	"raw_names" text[] DEFAULT '{""}' NOT NULL,
	"ror_id" text,
	"openalex_id" text,
	"geocode_status" text DEFAULT 'pending' NOT NULL,
	"geocode_query" text,
	"geocode_source" text,
	"geocode_raw" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"country_code" text,
	"country" text,
	"region" text,
	"city" text,
	"lat" double precision,
	"lon" double precision,
	"geom" geometry(Point,4326) GENERATED ALWAYS AS (
CASE
    WHEN ((lat IS NOT NULL) AND (lon IS NOT NULL)) THEN st_setsrid(st_makepoint(lon, lat), 4326)
    ELSE NULL::geometry
END) STORED,
	"geocoded_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "institutions_institution_key_key" UNIQUE("institution_key"),
	CONSTRAINT "institutions_geocode_status_check" CHECK (geocode_status = ANY (ARRAY['pending'::text, 'resolved'::text, 'failed'::text, 'ambiguous'::text, 'skip'::text])),
	CONSTRAINT "institutions_lat_check" CHECK ((lat IS NULL) OR ((lat >= ('-90'::integer)::double precision) AND (lat <= (90)::double precision))),
	CONSTRAINT "institutions_lon_check" CHECK ((lon IS NULL) OR ((lon >= ('-180'::integer)::double precision) AND (lon <= (180)::double precision))),
	CONSTRAINT "institutions_check" CHECK (((lat IS NULL) AND (lon IS NULL)) OR ((lat IS NOT NULL) AND (lon IS NOT NULL)))
);
--> statement-breakpoint
CREATE TABLE "paper_author_institutions" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"paper_author_id" bigint NOT NULL,
	"institution_id" bigint NOT NULL,
	"raw_affiliation" text,
	"affiliation_position" integer,
	"extraction_source" text,
	"extraction_confidence" numeric(4, 3),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "paper_author_institutions_paper_author_id_institution_id_key" UNIQUE("institution_id","paper_author_id")
);
--> statement-breakpoint
CREATE TABLE "arxiv_paper_categories" (
	"arxiv_id" text NOT NULL,
	"category" text NOT NULL,
	"is_primary" boolean DEFAULT false NOT NULL,
	CONSTRAINT "arxiv_paper_categories_pkey" PRIMARY KEY("arxiv_id","category")
);
--> statement-breakpoint
ALTER TABLE "paper_authors" ADD CONSTRAINT "paper_authors_arxiv_id_fkey" FOREIGN KEY ("arxiv_id") REFERENCES "public"."arxiv_papers"("arxiv_id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "paper_author_institutions" ADD CONSTRAINT "paper_author_institutions_paper_author_id_fkey" FOREIGN KEY ("paper_author_id") REFERENCES "public"."paper_authors"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "paper_author_institutions" ADD CONSTRAINT "paper_author_institutions_institution_id_fkey" FOREIGN KEY ("institution_id") REFERENCES "public"."institutions"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "arxiv_paper_categories" ADD CONSTRAINT "arxiv_paper_categories_arxiv_id_fkey" FOREIGN KEY ("arxiv_id") REFERENCES "public"."arxiv_papers"("arxiv_id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_arxiv_papers_categories_gin" ON "arxiv_papers" USING gin ("categories" array_ops);--> statement-breakpoint
CREATE INDEX "idx_arxiv_papers_primary_category" ON "arxiv_papers" USING btree ("primary_category" text_ops);--> statement-breakpoint
CREATE INDEX "idx_paper_authors_arxiv_id" ON "paper_authors" USING btree ("arxiv_id" text_ops);--> statement-breakpoint
CREATE INDEX "idx_institutions_country_code" ON "institutions" USING btree ("country_code" text_ops);--> statement-breakpoint
CREATE INDEX "idx_institutions_geocode_status" ON "institutions" USING btree ("geocode_status" text_ops);--> statement-breakpoint
CREATE INDEX "idx_institutions_geom" ON "institutions" USING gist ("geom" gist_geometry_ops_2d) WHERE (geom IS NOT NULL);--> statement-breakpoint
CREATE INDEX "idx_institutions_lat_lon" ON "institutions" USING btree ("lat" float8_ops,"lon" float8_ops) WHERE ((lat IS NOT NULL) AND (lon IS NOT NULL));--> statement-breakpoint
CREATE INDEX "idx_paper_author_institutions_author_id" ON "paper_author_institutions" USING btree ("paper_author_id" int8_ops);--> statement-breakpoint
CREATE INDEX "idx_paper_author_institutions_institution_id" ON "paper_author_institutions" USING btree ("institution_id" int8_ops);--> statement-breakpoint
CREATE INDEX "idx_arxiv_paper_categories_category" ON "arxiv_paper_categories" USING btree ("category" text_ops);--> statement-breakpoint
CREATE VIEW "public"."geography_columns" AS (SELECT current_database() AS f_table_catalog, n.nspname AS f_table_schema, c.relname AS f_table_name, a.attname AS f_geography_column, postgis_typmod_dims(a.atttypmod) AS coord_dimension, postgis_typmod_srid(a.atttypmod) AS srid, postgis_typmod_type(a.atttypmod) AS type FROM pg_class c, pg_attribute a, pg_type t, pg_namespace n WHERE t.typname = 'geography'::name AND a.attisdropped = false AND a.atttypid = t.oid AND a.attrelid = c.oid AND c.relnamespace = n.oid AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'm'::"char", 'f'::"char", 'p'::"char"])) AND NOT pg_is_other_temp_schema(c.relnamespace) AND has_table_privilege(c.oid, 'SELECT'::text));--> statement-breakpoint
CREATE VIEW "public"."geometry_columns" AS (SELECT current_database()::character varying(256) AS f_table_catalog, n.nspname AS f_table_schema, c.relname AS f_table_name, a.attname AS f_geometry_column, COALESCE(postgis_typmod_dims(a.atttypmod), sn.ndims, 2) AS coord_dimension, COALESCE(NULLIF(postgis_typmod_srid(a.atttypmod), 0), sr.srid, 0) AS srid, replace(replace(COALESCE(NULLIF(upper(postgis_typmod_type(a.atttypmod)), 'GEOMETRY'::text), st.type, 'GEOMETRY'::text), 'ZM'::text, ''::text), 'Z'::text, ''::text)::character varying(30) AS type FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid AND NOT a.attisdropped JOIN pg_namespace n ON c.relnamespace = n.oid JOIN pg_type t ON a.atttypid = t.oid LEFT JOIN ( SELECT s.connamespace, s.conrelid, s.conkey, (regexp_match(s.consrc, 'geometrytype\(\w+\)\s*=\s*''(\w+)'''::text, 'i'::text))[1] AS type FROM ( SELECT pg_constraint.connamespace, pg_constraint.conrelid, pg_constraint.conkey, pg_get_constraintdef(pg_constraint.oid) AS consrc FROM pg_constraint) s WHERE s.consrc ~* 'geometrytype\(\w+\)\s*=\s*''\w+'''::text) st ON st.connamespace = n.oid AND st.conrelid = c.oid AND (a.attnum = ANY (st.conkey)) LEFT JOIN ( SELECT s.connamespace, s.conrelid, s.conkey, (regexp_match(s.consrc, 'ndims\(\w+\)\s*=\s*(\d+)'::text, 'i'::text))[1]::integer AS ndims FROM ( SELECT pg_constraint.connamespace, pg_constraint.conrelid, pg_constraint.conkey, pg_get_constraintdef(pg_constraint.oid) AS consrc FROM pg_constraint) s WHERE s.consrc ~* 'ndims\(\w+\)\s*=\s*\d+'::text) sn ON sn.connamespace = n.oid AND sn.conrelid = c.oid AND (a.attnum = ANY (sn.conkey)) LEFT JOIN ( SELECT s.connamespace, s.conrelid, s.conkey, (regexp_match(s.consrc, 'srid\(\w+\)\s*=\s*(\d+)'::text, 'i'::text))[1]::integer AS srid FROM ( SELECT pg_constraint.connamespace, pg_constraint.conrelid, pg_constraint.conkey, pg_get_constraintdef(pg_constraint.oid) AS consrc FROM pg_constraint) s WHERE s.consrc ~* 'srid\(\w+\)\s*=\s*\d+'::text) sr ON sr.connamespace = n.oid AND sr.conrelid = c.oid AND (a.attnum = ANY (sr.conkey)) WHERE (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'm'::"char", 'f'::"char", 'p'::"char"])) AND NOT c.relname = 'raster_columns'::name AND t.typname = 'geometry'::name AND NOT pg_is_other_temp_schema(c.relnamespace) AND has_table_privilege(c.oid, 'SELECT'::text));--> statement-breakpoint
CREATE VIEW "public"."core_arxiv_table" AS (SELECT arxiv_id, title, abstract, doi, journal_ref, primary_category, categories, published_at, updated_at, raw_metadata, COALESCE(( SELECT jsonb_agg(jsonb_build_object('author_id', a.id, 'position', a.author_position, 'raw_name', a.raw_name, 'normalized_name', a.normalized_name, 'institutions', COALESCE(( SELECT jsonb_agg(jsonb_build_object('institution_id', i.id, 'institution_key', i.institution_key, 'display_name', i.display_name, 'raw_affiliation', pai.raw_affiliation, 'city', i.city, 'region', i.region, 'country', i.country, 'country_code', i.country_code, 'lat', i.lat, 'lon', i.lon, 'geometry', CASE WHEN i.geom IS NOT NULL THEN st_asgeojson(i.geom)::jsonb ELSE NULL::jsonb END, 'geocode_status', i.geocode_status) ORDER BY pai.affiliation_position, i.display_name) AS jsonb_agg FROM paper_author_institutions pai JOIN institutions i ON i.id = pai.institution_id WHERE pai.paper_author_id = a.id), '[]'::jsonb)) ORDER BY a.author_position) AS jsonb_agg FROM paper_authors a WHERE a.arxiv_id = p.arxiv_id), '[]'::jsonb) AS authors FROM arxiv_papers p);--> statement-breakpoint
CREATE MATERIALIZED VIEW "public"."arxiv_network_nodes_by_category" AS (WITH paper_category_rows AS ( SELECT arxiv_paper_categories.arxiv_id, arxiv_paper_categories.category FROM arxiv_paper_categories UNION ALL SELECT arxiv_papers.arxiv_id, '__all__'::text AS category FROM arxiv_papers ), paper_institutions AS ( SELECT DISTINCT pcr.category, pcr.arxiv_id, pai.institution_id FROM paper_category_rows pcr JOIN paper_authors pa ON pa.arxiv_id = pcr.arxiv_id JOIN paper_author_institutions pai ON pai.paper_author_id = pa.id JOIN institutions i_1 ON i_1.id = pai.institution_id WHERE i_1.geocode_status = 'resolved'::text AND i_1.geom IS NOT NULL ) SELECT pi.category, i.id AS institution_id, i.institution_key, i.display_name, i.city, i.region, i.country, i.country_code, i.lat, i.lon, i.geom, st_asgeojson(i.geom)::jsonb AS geometry, count(DISTINCT pi.arxiv_id)::integer AS paper_count FROM paper_institutions pi JOIN institutions i ON i.id = pi.institution_id GROUP BY pi.category, i.id, i.institution_key, i.display_name, i.city, i.region, i.country, i.country_code, i.lat, i.lon, i.geom);--> statement-breakpoint
CREATE MATERIALIZED VIEW "public"."arxiv_network_edges_by_category" AS (WITH paper_category_rows AS ( SELECT arxiv_paper_categories.arxiv_id, arxiv_paper_categories.category FROM arxiv_paper_categories UNION ALL SELECT arxiv_papers.arxiv_id, '__all__'::text AS category FROM arxiv_papers ), paper_institutions AS ( SELECT DISTINCT pcr.category, pcr.arxiv_id, p.published_at, pai.institution_id FROM paper_category_rows pcr JOIN arxiv_papers p ON p.arxiv_id = pcr.arxiv_id JOIN paper_authors pa ON pa.arxiv_id = pcr.arxiv_id JOIN paper_author_institutions pai ON pai.paper_author_id = pa.id JOIN institutions i ON i.id = pai.institution_id WHERE i.geocode_status = 'resolved'::text AND i.geom IS NOT NULL ), institution_pairs AS ( SELECT pi1.category, pi1.arxiv_id, pi1.published_at, pi1.institution_id AS source_institution_id, pi2.institution_id AS target_institution_id FROM paper_institutions pi1 JOIN paper_institutions pi2 ON pi1.category = pi2.category AND pi1.arxiv_id = pi2.arxiv_id AND pi1.institution_id < pi2.institution_id ) SELECT ip.category, ip.source_institution_id, source_i.display_name AS source_name, source_i.city AS source_city, source_i.region AS source_region, source_i.country AS source_country, source_i.country_code AS source_country_code, source_i.lat AS source_lat, source_i.lon AS source_lon, ip.target_institution_id, target_i.display_name AS target_name, target_i.city AS target_city, target_i.region AS target_region, target_i.country AS target_country, target_i.country_code AS target_country_code, target_i.lat AS target_lat, target_i.lon AS target_lon, st_makeline(source_i.geom, target_i.geom) AS geom, st_asgeojson(st_makeline(source_i.geom, target_i.geom))::jsonb AS geometry, count(DISTINCT ip.arxiv_id)::integer AS edge_weight, min(ip.published_at) AS first_paper_at, max(ip.published_at) AS latest_paper_at, array_agg(DISTINCT ip.arxiv_id ORDER BY ip.arxiv_id) AS sample_arxiv_ids FROM institution_pairs ip JOIN institutions source_i ON source_i.id = ip.source_institution_id JOIN institutions target_i ON target_i.id = ip.target_institution_id GROUP BY ip.category, ip.source_institution_id, source_i.display_name, source_i.city, source_i.region, source_i.country, source_i.country_code, source_i.lat, source_i.lon, source_i.geom, ip.target_institution_id, target_i.display_name, target_i.city, target_i.region, target_i.country, target_i.country_code, target_i.lat, target_i.lon, target_i.geom);
*/