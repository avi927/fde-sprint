-- Keyword (full-text) search: a tsvector kept up to date automatically from title + content.
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) STORED;

CREATE INDEX IF NOT EXISTS documents_search_tsv_idx
    ON documents USING gin (search_tsv);