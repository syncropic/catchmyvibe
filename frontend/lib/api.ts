import axios from 'axios'
import type {
  Track,
  TrackDetail,
  TrackListResponse,
  TrackSearchParams,
  Playlist,
  PlaylistDetail,
  DJSession,
  DJSessionDetail,
  ImportJob,
  AnalysisStats,
  SimilarTrackRequest,
  SimilarTrackResponse,
} from './types'

const client = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const api = {
  // Tracks
  async getTracks(params: TrackSearchParams = {}): Promise<TrackListResponse> {
    const { data } = await client.get('/tracks', { params })
    return data
  },

  async getTrack(id: string): Promise<TrackDetail> {
    const { data } = await client.get(`/tracks/${id}`)
    return data
  },

  async createTrack(track: Partial<Track>): Promise<Track> {
    const { data } = await client.post('/tracks', track)
    return data
  },

  async updateTrack(id: string, track: Partial<Track>): Promise<Track> {
    const { data } = await client.patch(`/tracks/${id}`, track)
    return data
  },

  async deleteTrack(id: string): Promise<void> {
    await client.delete(`/tracks/${id}`)
  },

  async findSimilarTracks(request: SimilarTrackRequest): Promise<SimilarTrackResponse> {
    const { data } = await client.post('/tracks/similar', request)
    return data
  },

  // Playlists
  async getPlaylists(parentId?: string): Promise<Playlist[]> {
    const params = parentId ? { parent_id: parentId } : {}
    const { data } = await client.get('/playlists', { params })
    return data
  },

  async getPlaylist(id: string): Promise<PlaylistDetail> {
    const { data } = await client.get(`/playlists/${id}`)
    return data
  },

  async createPlaylist(playlist: { name: string; description?: string; parent_id?: string }): Promise<Playlist> {
    const { data } = await client.post('/playlists', playlist)
    return data
  },

  async updatePlaylist(id: string, playlist: Partial<Playlist>): Promise<Playlist> {
    const { data } = await client.patch(`/playlists/${id}`, playlist)
    return data
  },

  async deletePlaylist(id: string): Promise<void> {
    await client.delete(`/playlists/${id}`)
  },

  async addTrackToPlaylist(playlistId: string, trackId: string, position?: number): Promise<void> {
    const params = position !== undefined ? { position } : {}
    await client.post(`/playlists/${playlistId}/tracks/${trackId}`, null, { params })
  },

  async removeTrackFromPlaylist(playlistId: string, trackId: string): Promise<void> {
    await client.delete(`/playlists/${playlistId}/tracks/${trackId}`)
  },

  // Sessions
  async getSessions(): Promise<DJSession[]> {
    const { data } = await client.get('/sessions')
    return data
  },

  async getSession(id: string): Promise<DJSessionDetail> {
    const { data } = await client.get(`/sessions/${id}`)
    return data
  },

  async createSession(session: Partial<DJSession>): Promise<DJSession> {
    const { data } = await client.post('/sessions', session)
    return data
  },

  async startSession(id: string): Promise<DJSession> {
    const { data } = await client.post(`/sessions/${id}/start`)
    return data
  },

  async endSession(id: string): Promise<DJSession> {
    const { data } = await client.post(`/sessions/${id}/end`)
    return data
  },

  // Import
  async importRekordbox(file: File): Promise<ImportJob> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await client.post('/import/rekordbox', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async importSerato(cratesPath?: string): Promise<ImportJob> {
    const { data } = await client.post('/import/serato', { crates_path: cratesPath })
    return data
  },

  async getImportJob(id: string): Promise<ImportJob> {
    const { data } = await client.get(`/import/jobs/${id}`)
    return data
  },

  async getImportJobs(): Promise<ImportJob[]> {
    const { data } = await client.get('/import/jobs')
    return data
  },

  // Analysis
  async getAnalysisStats(): Promise<AnalysisStats> {
    const { data } = await client.get('/analysis/stats')
    return data
  },

  async queueAnalysis(trackIds: string[], force = false): Promise<{ job_id: string; tracks_queued: number }> {
    const { data } = await client.post('/analysis/analyze', { track_ids: trackIds, force })
    return data
  },

  async queueEnrichment(trackIds?: string[]): Promise<{ job_id: string; tracks_queued: number }> {
    const { data } = await client.post('/analysis/enrich', { track_ids: trackIds })
    return data
  },
}

// Helper functions
export function formatDuration(ms: number | undefined): string {
  if (!ms) return '--:--'
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export function formatBPM(bpm: number | undefined): string {
  if (!bpm) return '--'
  return bpm.toFixed(1)
}

export function getKeyColor(key: string | undefined): string {
  if (!key) return 'bg-gray-700'
  const letter = key.slice(-1).toUpperCase()
  return letter === 'A' ? 'key-badge-a' : 'key-badge-b'
}

export function getEnergyLevel(energy: number | undefined): 'low' | 'mid' | 'high' {
  if (!energy) return 'mid'
  if (energy < 0.4) return 'low'
  if (energy > 0.7) return 'high'
  return 'mid'
}
