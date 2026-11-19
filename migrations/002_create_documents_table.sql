-- Knowledge base documents with their embeddings.
CREATE TABLE IF NOT EXISTS documents (
    id          bigserial    PRIMARY KEY,
    slug        text         NOT NULL UNIQUE,
    title       text         NOT NULL,
    content     text         NOT NULL,
    metadata    jsonb        NOT NULL DEFAULT '{}'::jsonb,
    embedding   vector(384)  NOT NULL,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);