CREATE TABLE IF NOT EXISTS cards (
    id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    quadrant_id  UUID        NOT NULL REFERENCES quadrants(id) ON DELETE CASCADE,
    content      TEXT        NOT NULL DEFAULT '',
    order_index  INTEGER     NOT NULL DEFAULT 0,
    author_id    TEXT,
    deleted_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Required for Realtime to emit full row data on UPDATE events
ALTER TABLE cards REPLICA IDENTITY FULL;

-- Add cards to Supabase's built-in realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE cards;
