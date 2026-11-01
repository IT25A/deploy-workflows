-- First version of the schema. Add later changes as new files (002_..., 003_...), never edit this one.
CREATE TABLE IF NOT EXISTS notes (
	id SERIAL PRIMARY KEY,
	owner TEXT NOT NULL,
	text TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
