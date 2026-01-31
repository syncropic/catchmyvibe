'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'

interface SpotifyStatus {
  connected: boolean
  user: {
    id: string
    email: string
    name: string
  } | null
  last_sync: string | null
  tracks_synced: number
  is_expired: boolean
}

interface SyncStatus {
  job_id: string
  status: string
  total_tracks: number
  processed_tracks: number
  new_tracks: number
  updated_tracks: number
  skipped_tracks: number
  failed_tracks: number
  progress_percent: number
  error_message: string | null
}

export default function ImportPage() {
  const queryClient = useQueryClient()
  const searchParams = useSearchParams()
  const [syncJobId, setSyncJobId] = useState<string | null>(null)
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Check for OAuth callback params
  useEffect(() => {
    const spotifyStatus = searchParams.get('spotify')
    const user = searchParams.get('user')
    const error = searchParams.get('error')

    if (spotifyStatus === 'connected' && user) {
      setNotification({ type: 'success', message: `Connected to Spotify as ${user}` })
      queryClient.invalidateQueries({ queryKey: ['spotify-status'] })
    } else if (error) {
      setNotification({ type: 'error', message: `Spotify connection failed: ${error}` })
    }
  }, [searchParams, queryClient])

  // Fetch Spotify connection status
  const { data: spotifyStatus, isLoading: statusLoading } = useQuery<SpotifyStatus>({
    queryKey: ['spotify-status'],
    queryFn: async () => {
      const res = await fetch('/api/auth/spotify/status')
      if (!res.ok) throw new Error('Failed to fetch status')
      return res.json()
    },
  })

  // Fetch sync status if job is running
  const { data: syncStatus } = useQuery<SyncStatus>({
    queryKey: ['sync-status', syncJobId],
    queryFn: async () => {
      if (!syncJobId) throw new Error('No job ID')
      const res = await fetch(`/api/import/spotify/liked-songs/status/${syncJobId}`)
      if (!res.ok) throw new Error('Failed to fetch sync status')
      return res.json()
    },
    enabled: !!syncJobId,
    refetchInterval: syncJobId ? 2000 : false, // Poll every 2 seconds while syncing
  })

  // Stop polling when sync is complete
  useEffect(() => {
    if (syncStatus?.status === 'completed' || syncStatus?.status === 'failed') {
      queryClient.invalidateQueries({ queryKey: ['spotify-status'] })
      queryClient.invalidateQueries({ queryKey: ['tracks'] })
    }
  }, [syncStatus?.status, queryClient])

  // Start sync mutation
  const syncMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/import/spotify/liked-songs', { method: 'POST' })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || 'Failed to start sync')
      }
      return res.json()
    },
    onSuccess: (data) => {
      setSyncJobId(data.job_id)
      setNotification({ type: 'success', message: `Started syncing ${data.total_tracks} tracks` })
    },
    onError: (error: Error) => {
      setNotification({ type: 'error', message: error.message })
    },
  })

  // Disconnect mutation
  const disconnectMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/auth/spotify/disconnect', { method: 'POST' })
      if (!res.ok) throw new Error('Failed to disconnect')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spotify-status'] })
      setNotification({ type: 'success', message: 'Disconnected from Spotify' })
    },
  })

  const handleSpotifyConnect = () => {
    window.location.href = '/api/auth/spotify/login'
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Import Music</h1>
        <p className="text-gray-400 mt-1">Connect your music sources and import your library</p>
      </div>

      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg ${
            notification.type === 'success'
              ? 'bg-green-900/30 border border-green-700 text-green-300'
              : 'bg-red-900/30 border border-red-700 text-red-300'
          }`}
        >
          {notification.message}
          <button
            onClick={() => setNotification(null)}
            className="float-right text-current hover:opacity-70"
          >
            ×
          </button>
        </div>
      )}

      {/* Spotify Section */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-12 h-12 bg-[#1DB954] rounded-full flex items-center justify-center">
            <SpotifyIcon />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Spotify</h2>
            <p className="text-gray-400 text-sm">Import your liked songs and playlists</p>
          </div>
        </div>

        {statusLoading ? (
          <div className="text-gray-400">Loading...</div>
        ) : spotifyStatus?.connected ? (
          <div className="space-y-4">
            {/* Connected Status */}
            <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <div>
                  <p className="font-medium">Connected as {spotifyStatus.user?.name}</p>
                  <p className="text-sm text-gray-400">{spotifyStatus.user?.email}</p>
                </div>
              </div>
              <button
                onClick={() => disconnectMutation.mutate()}
                className="text-sm text-gray-400 hover:text-red-400 transition-colors"
              >
                Disconnect
              </button>
            </div>

            {/* Sync Stats */}
            {spotifyStatus.tracks_synced > 0 && (
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-vibe-400">{spotifyStatus.tracks_synced}</p>
                  <p className="text-sm text-gray-400">Tracks Synced</p>
                </div>
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-400">Last Sync</p>
                  <p className="text-sm">
                    {spotifyStatus.last_sync
                      ? new Date(spotifyStatus.last_sync).toLocaleDateString()
                      : 'Never'}
                  </p>
                </div>
              </div>
            )}

            {/* Sync Progress */}
            {syncStatus && syncStatus.status !== 'completed' && syncStatus.status !== 'failed' && (
              <div className="p-4 bg-gray-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Syncing...</span>
                  <span className="text-sm text-gray-400">
                    {syncStatus.processed_tracks} / {syncStatus.total_tracks}
                  </span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#1DB954] transition-all duration-300"
                    style={{ width: `${syncStatus.progress_percent}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>New: {syncStatus.new_tracks}</span>
                  <span>Updated: {syncStatus.updated_tracks}</span>
                  <span>Skipped: {syncStatus.skipped_tracks}</span>
                </div>
              </div>
            )}

            {/* Sync Complete */}
            {syncStatus?.status === 'completed' && (
              <div className="p-4 bg-green-900/20 border border-green-800 rounded-lg">
                <p className="font-medium text-green-400">Sync Complete!</p>
                <p className="text-sm text-gray-400 mt-1">
                  Added {syncStatus.new_tracks} new tracks, updated {syncStatus.updated_tracks} existing tracks.
                </p>
              </div>
            )}

            {/* Sync Failed */}
            {syncStatus?.status === 'failed' && (
              <div className="p-4 bg-red-900/20 border border-red-800 rounded-lg">
                <p className="font-medium text-red-400">Sync Failed</p>
                <p className="text-sm text-gray-400 mt-1">{syncStatus.error_message}</p>
              </div>
            )}

            {/* Sync Button */}
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending || (syncStatus?.status === 'syncing')}
              className="w-full py-3 bg-[#1DB954] hover:bg-[#1ed760] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              {syncMutation.isPending || syncStatus?.status === 'syncing'
                ? 'Syncing...'
                : 'Sync Liked Songs'}
            </button>
          </div>
        ) : (
          <button
            onClick={handleSpotifyConnect}
            className="w-full py-3 bg-[#1DB954] hover:bg-[#1ed760] rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            <SpotifyIcon />
            Connect Spotify
          </button>
        )}
      </div>

      {/* Other Import Options */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Rekordbox */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 bg-orange-600 rounded-full flex items-center justify-center text-xl">
              🎛️
            </div>
            <div>
              <h2 className="text-xl font-semibold">Rekordbox</h2>
              <p className="text-gray-400 text-sm">Import from XML export</p>
            </div>
          </div>
          <label className="block">
            <input
              type="file"
              accept=".xml"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (!file) return

                const formData = new FormData()
                formData.append('file', file)

                try {
                  const res = await fetch('/api/import/rekordbox', {
                    method: 'POST',
                    body: formData,
                  })
                  if (!res.ok) throw new Error('Upload failed')
                  setNotification({ type: 'success', message: 'Rekordbox import started' })
                } catch {
                  setNotification({ type: 'error', message: 'Failed to import Rekordbox library' })
                }
              }}
            />
            <span className="block w-full py-3 border border-gray-700 hover:border-gray-600 rounded-lg text-center cursor-pointer transition-colors">
              Upload XML File
            </span>
          </label>
        </div>

        {/* Serato */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-xl">
              💿
            </div>
            <div>
              <h2 className="text-xl font-semibold">Serato</h2>
              <p className="text-gray-400 text-sm">Import from local database</p>
            </div>
          </div>
          <button
            onClick={async () => {
              try {
                const res = await fetch('/api/import/serato', { method: 'POST' })
                if (!res.ok) throw new Error('Import failed')
                setNotification({ type: 'success', message: 'Serato import started' })
              } catch {
                setNotification({ type: 'error', message: 'Failed to import Serato library' })
              }
            }}
            className="w-full py-3 border border-gray-700 hover:border-gray-600 rounded-lg transition-colors"
          >
            Scan Serato Library
          </button>
        </div>
      </div>
    </div>
  )
}

function SpotifyIcon() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
    </svg>
  )
}
