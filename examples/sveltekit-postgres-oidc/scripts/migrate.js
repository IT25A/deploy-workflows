// Applies the SQL files in the folder "migrations" that have not been applied yet, in the order of their names.
// It runs every time the container starts (see the CMD of the Dockerfile) and does nothing when everything is current.
//
// Write new files as migrations/002_add_something.sql. NEVER edit a file that has already been applied:
// it is skipped. Make a new file instead.
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const folder = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'migrations');

const client = new pg.Client({
	host: process.env.POSTGRES_HOST,
	port: Number(process.env.POSTGRES_PORT ?? 5432),
	user: process.env.POSTGRES_USER,
	password: process.env.POSTGRES_PASSWORD,
	database: process.env.POSTGRES_DB
});

await client.connect();
try {
	// Only one migration run at a time, even if two containers start together.
	await client.query('SELECT pg_advisory_lock(7250001)');
	await client.query(
		`CREATE TABLE IF NOT EXISTS schema_migrations (
			name TEXT PRIMARY KEY,
			applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`
	);
	const applied = new Set((await client.query('SELECT name FROM schema_migrations')).rows.map((row) => row.name));
	const files = (await readdir(folder)).filter((name) => name.endsWith('.sql')).sort();

	for (const file of files) {
		if (applied.has(file)) continue;
		console.log(`applying ${file}`);
		const sql = await readFile(path.join(folder, file), 'utf8');
		await client.query('BEGIN');
		try {
			await client.query(sql);
			await client.query('INSERT INTO schema_migrations (name) VALUES ($1)', [file]);
			await client.query('COMMIT');
		} catch (error) {
			await client.query('ROLLBACK');
			throw error;
		}
	}
	console.log('database is up to date');
} finally {
	await client.end();
}
