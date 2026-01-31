'use client'

import { formatDuration, formatBPM, getKeyColor, getEnergyLevel } from '@/lib/api'
import type { Track } from '@/lib/types'

interface TrackListProps {
  tracks: Track[]
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSort?: (column: string) => void
  onTrackClick?: (track: Track) => void
}

export function TrackList({ tracks, sortBy, sortOrder, onSort, onTrackClick }: TrackListProps) {
  const getSortIndicator = (column: string) => {
    if (sortBy !== column) return null
    return sortOrder === 'asc' ? ' ↑' : ' ↓'
  }

  const handleHeaderClick = (column: string) => {
    if (onSort) {
      onSort(column)
    }
  }

  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-800 text-left text-sm text-gray-400">
            <th className="px-4 py-3 w-12">#</th>
            <th
              className="px-4 py-3 cursor-pointer hover:text-white transition-colors"
              onClick={() => handleHeaderClick('title')}
            >
              Title{getSortIndicator('title')}
            </th>
            <th className="px-4 py-3">Artist</th>
            <th
              className="px-4 py-3 w-24 cursor-pointer hover:text-white transition-colors text-center"
              onClick={() => handleHeaderClick('bpm')}
            >
              BPM{getSortIndicator('bpm')}
            </th>
            <th
              className="px-4 py-3 w-20 cursor-pointer hover:text-white transition-colors text-center"
              onClick={() => handleHeaderClick('key')}
            >
              Key{getSortIndicator('key')}
            </th>
            <th className="px-4 py-3 w-20 text-center">Energy</th>
            <th className="px-4 py-3 w-20 text-right">Duration</th>
            <th className="px-4 py-3 w-20 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {tracks.map((track, index) => (
            <TrackRow
              key={track.id}
              track={track}
              index={index + 1}
              onClick={() => onTrackClick?.(track)}
            />
          ))}
        </tbody>
      </table>

      {tracks.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No tracks found. Import your library to get started.
        </div>
      )}
    </div>
  )
}

interface TrackRowProps {
  track: Track
  index: number
  onClick?: () => void
}

function TrackRow({ track, index, onClick }: TrackRowProps) {
  const energyLevel = getEnergyLevel(track.energy)

  return (
    <tr
      className="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <td className="px-4 py-3 text-gray-500">{index}</td>
      <td className="px-4 py-3">
        <div className="flex flex-col">
          <span className="font-medium text-white">{track.title}</span>
          {track.album && (
            <span className="text-xs text-gray-500 mt-0.5">{track.album}</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-gray-300">
        {track.artists.join(', ') || 'Unknown Artist'}
      </td>
      <td className="px-4 py-3 text-center">
        <span className="font-mono text-vibe-400">{formatBPM(track.bpm)}</span>
      </td>
      <td className="px-4 py-3 text-center">
        {track.key ? (
          <span className={`key-badge ${getKeyColor(track.key)}`}>{track.key}</span>
        ) : (
          <span className="text-gray-600">--</span>
        )}
      </td>
      <td className="px-4 py-3">
        <EnergyBar energy={track.energy} />
      </td>
      <td className="px-4 py-3 text-right text-gray-400 font-mono text-sm">
        {formatDuration(track.duration_ms)}
      </td>
      <td className="px-4 py-3 text-center">
        <StatusIndicator analyzed={track.is_analyzed} enriched={track.is_enriched} />
      </td>
    </tr>
  )
}

function EnergyBar({ energy }: { energy?: number }) {
  if (energy === undefined) {
    return <div className="h-2 bg-gray-700 rounded-full" />
  }

  const level = getEnergyLevel(energy)
  const colorClass = {
    low: 'bg-green-500',
    mid: 'bg-yellow-500',
    high: 'bg-red-500',
  }[level]

  return (
    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
      <div
        className={`h-full ${colorClass} transition-all`}
        style={{ width: `${energy * 100}%` }}
      />
    </div>
  )
}

function StatusIndicator({ analyzed, enriched }: { analyzed: boolean; enriched: boolean }) {
  return (
    <div className="flex items-center justify-center gap-1">
      <div
        className={`w-2 h-2 rounded-full ${analyzed ? 'bg-green-500' : 'bg-gray-600'}`}
        title={analyzed ? 'Analyzed' : 'Not analyzed'}
      />
      <div
        className={`w-2 h-2 rounded-full ${enriched ? 'bg-vibe-500' : 'bg-gray-600'}`}
        title={enriched ? 'Enriched' : 'Not enriched'}
      />
    </div>
  )
}
