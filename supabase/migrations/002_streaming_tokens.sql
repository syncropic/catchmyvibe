-- Streaming service tokens table for OAuth
-- Stores access tokens for Spotify, Tidal, etc.

CREATE TABLE IF NOT EXISTS streaming_service_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Service identifier
    service VARCHAR(50) NOT NULL,

    -- User info from the service
    service_user_id VARCHAR(255),
    service_user_email VARCHAR(255),
    service_user_name VARCHAR(255),

    -- OAuth tokens
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) NOT NULL DEFAULT 'Bearer',

    -- Token expiry
    expires_at TIMESTAMPTZ,

    -- Scopes granted
    scopes TEXT,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    last_sync_at TIMESTAMPTZ,

    -- Sync stats
    tracks_synced INTEGER NOT NULL DEFAULT 0,
    playlists_synced INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_streaming_tokens_service ON streaming_service_tokens(service);
CREATE INDEX IF NOT EXISTS idx_streaming_tokens_service_user ON streaming_service_tokens(service, service_user_id);
CREATE INDEX IF NOT EXISTS idx_streaming_tokens_active ON streaming_service_tokens(is_active);

-- Trigger for updated_at
CREATE TRIGGER update_streaming_service_tokens_updated_at
    BEFORE UPDATE ON streaming_service_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comment
COMMENT ON TABLE streaming_service_tokens IS 'OAuth tokens for streaming services (Spotify, Tidal, etc.)';
