-- Chunks: pieces of documents, each with its own embedding and full-text vector.
CREATE TABLE IF NOT EXISTS chunks (
    id            bigserial    PRIMARY KEY,
    document_id   bigint       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_config  text         NOT NULL,
    chunk_index   integer      NOT NULL,
    content       text         NOT NULL,
    word_count    integer      NOT NULL,
    embedding     vector(384)  NOT NULL,
    search_tsv    tsvector     GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_config, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_search_tsv_idx
    ON chunks USING gin (search_tsv);

CREATE INDEX IF NOT EXISTS chunks_config_idx
    ON chunks (chunk_config);