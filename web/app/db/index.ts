import { config } from 'dotenv';
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';

import * as schema from './schema';

config({ path: '.env', quiet: true });
config({ path: 'app/.env', override: false, quiet: true });

if (!process.env.DATABASE_URL) {
    throw new Error('DATABASE_URL is required. Add it to web/app/.env or your shell environment.');
}

const globalForDb = globalThis as unknown as {
    pgPool?: Pool;
};

export const pool =
    globalForDb.pgPool ??
    new Pool({
        connectionString: process.env.DATABASE_URL,
    });

if (process.env.NODE_ENV !== 'production') {
    globalForDb.pgPool = pool;
}

export const db = drizzle(pool, { schema });

export type Db = typeof db;
