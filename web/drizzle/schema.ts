import { pgTable, index, text, timestamp, jsonb, foreignKey, unique, bigserial, integer, numeric, check, doublePrecision, geometry, bigint, primaryKey, boolean, pgView, pgMaterializedView } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



export const arxivPapers = pgTable("arxiv_papers", {
	arxivId: text("arxiv_id").primaryKey().notNull(),
	title: text().notNull(),
	abstract: text(),
	doi: text(),
	journalRef: text("journal_ref"),
	primaryCategory: text("primary_category"),
	categories: text().array().default([""]).notNull(),
	publishedAt: timestamp("published_at", { withTimezone: true, mode: 'string' }),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }),
	rawMetadata: jsonb("raw_metadata").default({}).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_arxiv_papers_categories_gin").using("gin", table.categories.asc().nullsLast().op("array_ops")),
	index("idx_arxiv_papers_primary_category").using("btree", table.primaryCategory.asc().nullsLast().op("text_ops")),
]);

export const paperAuthors = pgTable("paper_authors", {
	id: bigserial({ mode: "bigint" }).primaryKey().notNull(),
	arxivId: text("arxiv_id").notNull(),
	authorPosition: integer("author_position").notNull(),
	rawName: text("raw_name").notNull(),
	normalizedName: text("normalized_name"),
	extractionSource: text("extraction_source"),
	extractionConfidence: numeric("extraction_confidence", { precision: 4, scale:  3 }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_paper_authors_arxiv_id").using("btree", table.arxivId.asc().nullsLast().op("text_ops")),
	foreignKey({
			columns: [table.arxivId],
			foreignColumns: [arxivPapers.arxivId],
			name: "paper_authors_arxiv_id_fkey"
		}).onDelete("cascade"),
	unique("paper_authors_arxiv_id_author_position_key").on(table.arxivId, table.authorPosition),
]);

export const institutions = pgTable("institutions", {
	id: bigserial({ mode: "bigint" }).primaryKey().notNull(),
	institutionKey: text("institution_key").notNull(),
	displayName: text("display_name").notNull(),
	rawNames: text("raw_names").array().default([""]).notNull(),
	rorId: text("ror_id"),
	openalexId: text("openalex_id"),
	geocodeStatus: text("geocode_status").default('pending').notNull(),
	geocodeQuery: text("geocode_query"),
	geocodeSource: text("geocode_source"),
	geocodeRaw: jsonb("geocode_raw").default({}).notNull(),
	countryCode: text("country_code"),
	country: text(),
	region: text(),
	city: text(),
	lat: doublePrecision(),
	lon: doublePrecision(),
	geom: geometry({ type: "point", srid: 4326 }).generatedAlwaysAs(sql`
CASE
    WHEN ((lat IS NOT NULL) AND (lon IS NOT NULL)) THEN st_setsrid(st_makepoint(lon, lat), 4326)
    ELSE NULL::geometry
END`),
	geocodedAt: timestamp("geocoded_at", { withTimezone: true, mode: 'string' }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_institutions_country_code").using("btree", table.countryCode.asc().nullsLast().op("text_ops")),
	index("idx_institutions_geocode_status").using("btree", table.geocodeStatus.asc().nullsLast().op("text_ops")),
	index("idx_institutions_geom").using("gist", table.geom.asc().nullsLast().op("gist_geometry_ops_2d")).where(sql`(geom IS NOT NULL)`),
	index("idx_institutions_lat_lon").using("btree", table.lat.asc().nullsLast().op("float8_ops"), table.lon.asc().nullsLast().op("float8_ops")).where(sql`((lat IS NOT NULL) AND (lon IS NOT NULL))`),
	unique("institutions_institution_key_key").on(table.institutionKey),
	check("institutions_geocode_status_check", sql`geocode_status = ANY (ARRAY['pending'::text, 'resolved'::text, 'failed'::text, 'ambiguous'::text, 'skip'::text])`),
	check("institutions_lat_check", sql`(lat IS NULL) OR ((lat >= ('-90'::integer)::double precision) AND (lat <= (90)::double precision))`),
	check("institutions_lon_check", sql`(lon IS NULL) OR ((lon >= ('-180'::integer)::double precision) AND (lon <= (180)::double precision))`),
	check("institutions_check", sql`((lat IS NULL) AND (lon IS NULL)) OR ((lat IS NOT NULL) AND (lon IS NOT NULL))`),
]);

export const paperAuthorInstitutions = pgTable("paper_author_institutions", {
	id: bigserial({ mode: "bigint" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	paperAuthorId: bigint("paper_author_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	institutionId: bigint("institution_id", { mode: "number" }).notNull(),
	rawAffiliation: text("raw_affiliation"),
	affiliationPosition: integer("affiliation_position"),
	extractionSource: text("extraction_source"),
	extractionConfidence: numeric("extraction_confidence", { precision: 4, scale:  3 }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_paper_author_institutions_author_id").using("btree", table.paperAuthorId.asc().nullsLast().op("int8_ops")),
	index("idx_paper_author_institutions_institution_id").using("btree", table.institutionId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.paperAuthorId],
			foreignColumns: [paperAuthors.id],
			name: "paper_author_institutions_paper_author_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.institutionId],
			foreignColumns: [institutions.id],
			name: "paper_author_institutions_institution_id_fkey"
		}).onDelete("cascade"),
	unique("paper_author_institutions_paper_author_id_institution_id_key").on(table.institutionId, table.paperAuthorId),
]);

export const arxivPaperCategories = pgTable("arxiv_paper_categories", {
	arxivId: text("arxiv_id").notNull(),
	category: text().notNull(),
	isPrimary: boolean("is_primary").default(false).notNull(),
}, (table) => [
	index("idx_arxiv_paper_categories_category").using("btree", table.category.asc().nullsLast().op("text_ops")),
	foreignKey({
			columns: [table.arxivId],
			foreignColumns: [arxivPapers.arxivId],
			name: "arxiv_paper_categories_arxiv_id_fkey"
		}).onDelete("cascade"),
	primaryKey({ columns: [table.arxivId, table.category], name: "arxiv_paper_categories_pkey"}),
]);
export const coreArxivTable = pgView("core_arxiv_table", {	arxivId: text("arxiv_id"),
	title: text(),
	abstract: text(),
	doi: text(),
	journalRef: text("journal_ref"),
	primaryCategory: text("primary_category"),
	categories: text(),
	publishedAt: timestamp("published_at", { withTimezone: true, mode: 'string' }),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }),
	rawMetadata: jsonb("raw_metadata"),
	authors: jsonb(),
}).as(sql`SELECT arxiv_id, title, abstract, doi, journal_ref, primary_category, categories, published_at, updated_at, raw_metadata, COALESCE(( SELECT jsonb_agg(jsonb_build_object('author_id', a.id, 'position', a.author_position, 'raw_name', a.raw_name, 'normalized_name', a.normalized_name, 'institutions', COALESCE(( SELECT jsonb_agg(jsonb_build_object('institution_id', i.id, 'institution_key', i.institution_key, 'display_name', i.display_name, 'raw_affiliation', pai.raw_affiliation, 'city', i.city, 'region', i.region, 'country', i.country, 'country_code', i.country_code, 'lat', i.lat, 'lon', i.lon, 'geometry', CASE WHEN i.geom IS NOT NULL THEN st_asgeojson(i.geom)::jsonb ELSE NULL::jsonb END, 'geocode_status', i.geocode_status) ORDER BY pai.affiliation_position, i.display_name) AS jsonb_agg FROM paper_author_institutions pai JOIN institutions i ON i.id = pai.institution_id WHERE pai.paper_author_id = a.id), '[]'::jsonb)) ORDER BY a.author_position) AS jsonb_agg FROM paper_authors a WHERE a.arxiv_id = p.arxiv_id), '[]'::jsonb) AS authors FROM arxiv_papers p`);

export const arxivNetworkNodesByCategory = pgMaterializedView("arxiv_network_nodes_by_category", {	category: text(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	institutionId: bigint("institution_id", { mode: "number" }),
	institutionKey: text("institution_key"),
	displayName: text("display_name"),
	city: text(),
	region: text(),
	country: text(),
	countryCode: text("country_code"),
	lat: doublePrecision(),
	lon: doublePrecision(),
	geom: geometry({ type: "point", srid: 4326 }),
	geometry: jsonb(),
	paperCount: integer("paper_count"),
}).as(sql`WITH paper_category_rows AS ( SELECT arxiv_paper_categories.arxiv_id, arxiv_paper_categories.category FROM arxiv_paper_categories UNION ALL SELECT arxiv_papers.arxiv_id, '__all__'::text AS category FROM arxiv_papers ), paper_institutions AS ( SELECT DISTINCT pcr.category, pcr.arxiv_id, pai.institution_id FROM paper_category_rows pcr JOIN paper_authors pa ON pa.arxiv_id = pcr.arxiv_id JOIN paper_author_institutions pai ON pai.paper_author_id = pa.id JOIN institutions i_1 ON i_1.id = pai.institution_id WHERE i_1.geocode_status = 'resolved'::text AND i_1.geom IS NOT NULL ) SELECT pi.category, i.id AS institution_id, i.institution_key, i.display_name, i.city, i.region, i.country, i.country_code, i.lat, i.lon, i.geom, st_asgeojson(i.geom)::jsonb AS geometry, count(DISTINCT pi.arxiv_id)::integer AS paper_count FROM paper_institutions pi JOIN institutions i ON i.id = pi.institution_id GROUP BY pi.category, i.id, i.institution_key, i.display_name, i.city, i.region, i.country, i.country_code, i.lat, i.lon, i.geom`);

export const arxivNetworkEdgesByCategory = pgMaterializedView("arxiv_network_edges_by_category", {	category: text(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	sourceInstitutionId: bigint("source_institution_id", { mode: "number" }),
	sourceName: text("source_name"),
	sourceCity: text("source_city"),
	sourceRegion: text("source_region"),
	sourceCountry: text("source_country"),
	sourceCountryCode: text("source_country_code"),
	sourceLat: doublePrecision("source_lat"),
	sourceLon: doublePrecision("source_lon"),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	targetInstitutionId: bigint("target_institution_id", { mode: "number" }),
	targetName: text("target_name"),
	targetCity: text("target_city"),
	targetRegion: text("target_region"),
	targetCountry: text("target_country"),
	targetCountryCode: text("target_country_code"),
	targetLat: doublePrecision("target_lat"),
	targetLon: doublePrecision("target_lon"),
	geom: geometry(),
	geometry: jsonb(),
	edgeWeight: integer("edge_weight"),
	firstPaperAt: timestamp("first_paper_at", { withTimezone: true, mode: 'string' }),
	latestPaperAt: timestamp("latest_paper_at", { withTimezone: true, mode: 'string' }),
	sampleArxivIds: text("sample_arxiv_ids"),
}).as(sql`WITH paper_category_rows AS ( SELECT arxiv_paper_categories.arxiv_id, arxiv_paper_categories.category FROM arxiv_paper_categories UNION ALL SELECT arxiv_papers.arxiv_id, '__all__'::text AS category FROM arxiv_papers ), paper_institutions AS ( SELECT DISTINCT pcr.category, pcr.arxiv_id, p.published_at, pai.institution_id FROM paper_category_rows pcr JOIN arxiv_papers p ON p.arxiv_id = pcr.arxiv_id JOIN paper_authors pa ON pa.arxiv_id = pcr.arxiv_id JOIN paper_author_institutions pai ON pai.paper_author_id = pa.id JOIN institutions i ON i.id = pai.institution_id WHERE i.geocode_status = 'resolved'::text AND i.geom IS NOT NULL ), institution_pairs AS ( SELECT pi1.category, pi1.arxiv_id, pi1.published_at, pi1.institution_id AS source_institution_id, pi2.institution_id AS target_institution_id FROM paper_institutions pi1 JOIN paper_institutions pi2 ON pi1.category = pi2.category AND pi1.arxiv_id = pi2.arxiv_id AND pi1.institution_id < pi2.institution_id ) SELECT ip.category, ip.source_institution_id, source_i.display_name AS source_name, source_i.city AS source_city, source_i.region AS source_region, source_i.country AS source_country, source_i.country_code AS source_country_code, source_i.lat AS source_lat, source_i.lon AS source_lon, ip.target_institution_id, target_i.display_name AS target_name, target_i.city AS target_city, target_i.region AS target_region, target_i.country AS target_country, target_i.country_code AS target_country_code, target_i.lat AS target_lat, target_i.lon AS target_lon, st_makeline(source_i.geom, target_i.geom) AS geom, st_asgeojson(st_makeline(source_i.geom, target_i.geom))::jsonb AS geometry, count(DISTINCT ip.arxiv_id)::integer AS edge_weight, min(ip.published_at) AS first_paper_at, max(ip.published_at) AS latest_paper_at, array_agg(DISTINCT ip.arxiv_id ORDER BY ip.arxiv_id) AS sample_arxiv_ids FROM institution_pairs ip JOIN institutions source_i ON source_i.id = ip.source_institution_id JOIN institutions target_i ON target_i.id = ip.target_institution_id GROUP BY ip.category, ip.source_institution_id, source_i.display_name, source_i.city, source_i.region, source_i.country, source_i.country_code, source_i.lat, source_i.lon, source_i.geom, ip.target_institution_id, target_i.display_name, target_i.city, target_i.region, target_i.country, target_i.country_code, target_i.lat, target_i.lon, target_i.geom`);