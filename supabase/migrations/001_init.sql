CREATE TABLE IF NOT EXISTS workspaces (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    access_token UUID        NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_name TEXT        NOT NULL CHECK (char_length(project_name) > 0),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS canvases (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TYPE quadrant_type AS ENUM ('IS', 'IS_NOT', 'DOES', 'DOES_NOT');

CREATE TABLE IF NOT EXISTS quadrants (
    id         UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id  UUID           NOT NULL REFERENCES canvases(id) ON DELETE CASCADE,
    type       quadrant_type  NOT NULL,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (canvas_id, type)
);

-- Required for Realtime to emit full row data on UPDATE events
ALTER TABLE workspaces REPLICA IDENTITY FULL;

-- Add workspaces to Supabase's built-in realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE workspaces;
