// Track types
export interface Track {
  id: string
  title: string
  artists: string[]
  album?: string
  isrc?: string
  label?: string
  release_year?: number
  genre?: string
  bpm?: number
  key?: string
  duration_ms?: number
  energy?: number
  danceability?: number
  valence?: number
  acousticness?: number
  instrumentalness?: number
  speechiness?: number
  liveness?: number
  loudness?: number
  vibe_tags: string[]
  mix_in_point_ms?: number
  mix_out_point_ms?: number
  rating?: number
  play_count: number
  comment?: string
  cloud_uri?: string
  streaming_ids: Record<string, string>
  is_analyzed: boolean
  is_enriched: boolean
  created_at: string
  updated_at: string
}

export interface CuePoint {
  id: string
  track_id: string
  position_ms: number
  name?: string
  color?: string
  cue_type: string
  loop_end_ms?: number
  source: string
  created_at: string
}

export interface SourceLink {
  id: string
  track_id: string
  source: string
  external_id?: string
  uri?: string
  file_path?: string
  is_primary: boolean
}

export interface TrackDetail extends Track {
  cue_points: CuePoint[]
  source_links: SourceLink[]
}

export interface TrackListResponse {
  items: Track[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TrackSearchParams {
  query?: string
  bpm_min?: number
  bpm_max?: number
  key?: string
  keys?: string[]
  energy_min?: number
  energy_max?: number
  genre?: string
  genres?: string[]
  vibe_tags?: string[]
  is_analyzed?: boolean
  is_enriched?: boolean
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

// Playlist types
export interface Playlist {
  id: string
  name: string
  description?: string
  source: string
  is_folder: boolean
  parent_id?: string
  track_count: number
  total_duration_ms: number
  cover_art_url?: string
  created_at: string
  updated_at: string
}

export interface PlaylistDetail extends Playlist {
  tracks: Track[]
  children: Playlist[]
}

// Session types
export interface DJSession {
  id: string
  name: string
  venue?: string
  event_type?: string
  planned_duration_ms?: number
  notes?: string
  energy_profile?: string
  genre_focus: string[]
  started_at?: string
  ended_at?: string
  is_recorded: boolean
  track_count: number
  avg_bpm?: number
  created_at: string
  updated_at: string
}

export interface SessionTrack {
  id: string
  session_id: string
  track_id?: string
  position: number
  played_at?: string
  play_duration_ms?: number
  played_bpm?: number
  transition_type?: string
  transition_quality?: number
  transition_notes?: string
  crowd_energy?: number
  track?: Track
}

export interface DJSessionDetail extends DJSession {
  tracks: SessionTrack[]
}

// Import types
export interface ImportJob {
  id: string
  source: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  tracks_imported: number
  tracks_skipped: number
  tracks_failed: number
  error_message?: string
  started_at?: string
  completed_at?: string
}

// Analysis types
export interface AnalysisStats {
  total_tracks: number
  analyzed_tracks: number
  enriched_tracks: number
  tracks_with_embeddings: number
  analysis_percentage: number
  enrichment_percentage: number
}

// Similarity types
export interface SimilarTrackRequest {
  track_id: string
  limit?: number
  bpm_range?: number
  same_key?: boolean
  harmonic_keys?: boolean
}

export interface SimilarTrackResponse {
  source_track: Track
  similar_tracks: Track[]
  similarity_scores: number[]
}
