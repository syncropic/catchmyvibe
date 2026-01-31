-- CatchMyVibe Initial Schema
-- Run this on your PostgreSQL database to set up the schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Tracks table
CREATE TABLE IF NOT EXISTS tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    artists TEXT[] NOT NULL DEFAULT '{}',
    album VARCHAR(500),
    isrc VARCHAR(12) UNIQUE,
    label VARCHAR(255),
    release_year INTEGER,
    genre VARCHAR(100),

    -- Audio properties
    bpm FLOAT,
    key VARCHAR(10),
    duration_ms INTEGER,

    -- Analysis results
    energy FLOAT,
    danceability FLOAT,
    valence FLOAT,
    acousticness FLOAT,
    instrumentalness FLOAT,
    speechiness FLOAT,
    liveness FLOAT,
    loudness FLOAT,

    -- ML-generated
    vibe_tags TEXT[] NOT NULL DEFAULT '{}',
    embedding FLOAT[],

    -- DJ metadata
    mix_in_point_ms INTEGER,
    mix_out_point_ms INTEGER,
    rating INTEGER,
    play_count INTEGER NOT NULL DEFAULT 0,
    comment TEXT,

    -- Storage
    cloud_uri VARCHAR(1000),
    original_path VARCHAR(1000),
    streaming_ids JSONB NOT NULL DEFAULT '{}',
    waveform_data FLOAT[],

    -- Status
    is_analyzed BOOLEAN NOT NULL DEFAULT FALSE,
    is_enriched BOOLEAN NOT NULL DEFAULT FALSE,
    analysis_error TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cue points table
CREATE TABLE IF NOT EXISTS cue_points (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position_ms INTEGER NOT NULL,
    name VARCHAR(100),
    color VARCHAR(7),
    cue_type VARCHAR(20) NOT NULL DEFAULT 'cue',
    loop_end_ms INTEGER,
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Source links table
CREATE TABLE IF NOT EXISTS source_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    uri VARCHAR(1000),
    file_path VARCHAR(1000),
    file_hash VARCHAR(64),
    metadata_json JSONB NOT NULL DEFAULT '{}',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Playlists table
CREATE TABLE IF NOT EXISTS playlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    external_id VARCHAR(255),
    is_folder BOOLEAN NOT NULL DEFAULT FALSE,
    parent_id UUID REFERENCES playlists(id) ON DELETE CASCADE,
    cover_art_url VARCHAR(1000),
    track_count INTEGER NOT NULL DEFAULT 0,
    total_duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Playlist tracks junction table
CREATE TABLE IF NOT EXISTS playlist_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    playlist_id UUID NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_by VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(playlist_id, track_id)
);

-- DJ Sessions table
CREATE TABLE IF NOT EXISTS dj_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    venue VARCHAR(255),
    event_type VARCHAR(50),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    planned_duration_ms INTEGER,
    notes TEXT,
    energy_profile VARCHAR(50),
    genre_focus JSONB NOT NULL DEFAULT '[]',
    recording_path VARCHAR(1000),
    is_recorded BOOLEAN NOT NULL DEFAULT FALSE,
    track_count INTEGER NOT NULL DEFAULT 0,
    avg_bpm FLOAT,
    bpm_range JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Session tracks table
CREATE TABLE IF NOT EXISTS session_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES dj_sessions(id) ON DELETE CASCADE,
    track_id UUID REFERENCES tracks(id) ON DELETE SET NULL,
    position INTEGER NOT NULL,
    played_at TIMESTAMPTZ,
    play_duration_ms INTEGER,
    played_bpm FLOAT,
    transition_type VARCHAR(50),
    transition_quality INTEGER,
    transition_notes TEXT,
    crowd_energy FLOAT,
    unmatched_title VARCHAR(500),
    unmatched_artist VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_isrc ON tracks(isrc);
CREATE INDEX IF NOT EXISTS idx_tracks_bpm ON tracks(bpm);
CREATE INDEX IF NOT EXISTS idx_tracks_key ON tracks(key);
CREATE INDEX IF NOT EXISTS idx_tracks_is_analyzed ON tracks(is_analyzed);
CREATE INDEX IF NOT EXISTS idx_tracks_is_enriched ON tracks(is_enriched);

CREATE INDEX IF NOT EXISTS idx_cue_points_track_id ON cue_points(track_id);
CREATE INDEX IF NOT EXISTS idx_source_links_track_id ON source_links(track_id);
CREATE INDEX IF NOT EXISTS idx_playlists_name ON playlists(name);
CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist_id ON playlist_tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track_id ON playlist_tracks(track_id);
CREATE INDEX IF NOT EXISTS idx_session_tracks_session_id ON session_tracks(session_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_tracks_updated_at BEFORE UPDATE ON tracks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cue_points_updated_at BEFORE UPDATE ON cue_points
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_source_links_updated_at BEFORE UPDATE ON source_links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_playlists_updated_at BEFORE UPDATE ON playlists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_playlist_tracks_updated_at BEFORE UPDATE ON playlist_tracks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dj_sessions_updated_at BEFORE UPDATE ON dj_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_tracks_updated_at BEFORE UPDATE ON session_tracks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Full-text search index for tracks
CREATE INDEX IF NOT EXISTS idx_tracks_fts ON tracks
    USING GIN (to_tsvector('english', title || ' ' || array_to_string(artists, ' ') || ' ' || COALESCE(album, '')));
