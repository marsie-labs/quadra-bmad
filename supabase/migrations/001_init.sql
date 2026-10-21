CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS workspaces (
    id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    access_token UUID        NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    project_name TEXT        NOT NULL CHECK (char_length(project_name) > 0),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS canvases (
    id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TYPE quadrant_type AS ENUM ('IS', 'IS_NOT', 'DOES', 'DOES_NOT');

CREATE TABLE IF NOT EXISTS quadrants (
    id         UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    canvas_id  UUID           NOT NULL REFERENCES canvases(id) ON DELETE CASCADE,
    type       quadrant_type  NOT NULL,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (canvas_id, type)
);

-- Required for Realtime to emit full row data on UPDATE events
ALTER TABLE workspaces REPLICA IDENTITY FULL;

-- Add workspaces to Supabase's built-in realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE workspaces;
