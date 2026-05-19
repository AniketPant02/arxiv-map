import { config } from 'dotenv';
import { defineConfig } from 'drizzle-kit';

config({ path: '.env', quiet: true });
config({ path: 'app/.env', override: false, quiet: true });

if (!process.env.DATABASE_URL) {
    throw new Error('DATABASE_URL is required. Add it to web/app/.env or your shell environment.');
}

export default defineConfig({
    out: './drizzle',
    schema: './drizzle/schema.ts',
    dialect: 'postgresql',
    introspect: {
        casing: 'camel',
    },
    tablesFilter: [
        'arxiv_papers',
        'arxiv_paper_categories',
        'paper_authors',
        'paper_author_institutions',
        'institutions',
        'core_arxiv_table',
        'arxiv_network_nodes_by_category',
        'arxiv_network_edges_by_category',
    ],
    dbCredentials: {
        url: process.env.DATABASE_URL,
    },
});
