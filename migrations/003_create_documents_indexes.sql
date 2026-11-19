-- Fast approximate nearest-neighbour search using cosine distance (the <=> operator).
CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
    ON documents USING hnsw (embedding vector_cosine_ops);

-- Fast metadata filters such as: metadata @> '{"category": "billing"}'
CREATE INDEX IF NOT EXISTS documents_metadata_gin_idx
    ON documents USING gin (metadata);