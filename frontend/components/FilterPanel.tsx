'use client'

import { useState } from 'react'
import type { TrackSearchParams } from '@/lib/types'

interface FilterPanelProps {
  filters: TrackSearchParams
  onFilterChange: (filters: Partial<TrackSearchParams>) => void
}

const CAMELOT_KEYS = [
  '1A', '1B', '2A', '2B', '3A', '3B', '4A', '4B',
  '5A', '5B', '6A', '6B', '7A', '7B', '8A', '8B',
  '9A', '9B', '10A', '10B', '11A', '11B', '12A', '12B',
]

export function FilterPanel({ filters, onFilterChange }: FilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const handleBpmChange = (type: 'min' | 'max', value: string) => {
    const numValue = value ? parseFloat(value) : undefined
    if (type === 'min') {
      onFilterChange({ bpm_min: numValue })
    } else {
      onFilterChange({ bpm_max: numValue })
    }
  }

  const handleKeyChange = (key: string) => {
    onFilterChange({ key: key || undefined })
  }

  const handleEnergyChange = (type: 'min' | 'max', value: string) => {
    const numValue = value ? parseFloat(value) : undefined
    if (type === 'min') {
      onFilterChange({ energy_min: numValue })
    } else {
      onFilterChange({ energy_max: numValue })
    }
  }

  const handleStatusChange = (field: 'is_analyzed' | 'is_enriched', value: string) => {
    const boolValue = value === '' ? undefined : value === 'true'
    onFilterChange({ [field]: boolValue })
  }

  const clearFilters = () => {
    onFilterChange({
      bpm_min: undefined,
      bpm_max: undefined,
      key: undefined,
      energy_min: undefined,
      energy_max: undefined,
      is_analyzed: undefined,
      is_enriched: undefined,
    })
  }

  const hasActiveFilters =
    filters.bpm_min !== undefined ||
    filters.bpm_max !== undefined ||
    filters.key !== undefined ||
    filters.energy_min !== undefined ||
    filters.energy_max !== undefined ||
    filters.is_analyzed !== undefined ||
    filters.is_enriched !== undefined

  return (
    <div className="relative">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`px-4 py-2.5 rounded-lg border transition-colors flex items-center gap-2 ${
          hasActiveFilters
            ? 'bg-vibe-900 border-vibe-700 text-vibe-300'
            : 'bg-gray-900 border-gray-700 text-gray-300 hover:border-gray-600'
        }`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="w-5 h-5"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75"
          />
        </svg>
        Filters
        {hasActiveFilters && (
          <span className="w-2 h-2 bg-vibe-500 rounded-full" />
        )}
      </button>

      {isExpanded && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-white">Filters</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-gray-400 hover:text-white transition-colors"
              >
                Clear all
              </button>
            )}
          </div>

          <div className="space-y-4">
            {/* BPM Range */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">BPM Range</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  value={filters.bpm_min ?? ''}
                  onChange={(e) => handleBpmChange('min', e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                />
                <span className="text-gray-500">-</span>
                <input
                  type="number"
                  placeholder="Max"
                  value={filters.bpm_max ?? ''}
                  onChange={(e) => handleBpmChange('max', e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                />
              </div>
            </div>

            {/* Key */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Key (Camelot)</label>
              <select
                value={filters.key ?? ''}
                onChange={(e) => handleKeyChange(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
              >
                <option value="">Any key</option>
                {CAMELOT_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </div>

            {/* Energy Range */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Energy (0-1)</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  min="0"
                  max="1"
                  step="0.1"
                  value={filters.energy_min ?? ''}
                  onChange={(e) => handleEnergyChange('min', e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                />
                <span className="text-gray-500">-</span>
                <input
                  type="number"
                  placeholder="Max"
                  min="0"
                  max="1"
                  step="0.1"
                  value={filters.energy_max ?? ''}
                  onChange={(e) => handleEnergyChange('max', e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                />
              </div>
            </div>

            {/* Status Filters */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Analyzed</label>
                <select
                  value={filters.is_analyzed === undefined ? '' : String(filters.is_analyzed)}
                  onChange={(e) => handleStatusChange('is_analyzed', e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                >
                  <option value="">Any</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-2">Enriched</label>
                <select
                  value={filters.is_enriched === undefined ? '' : String(filters.is_enriched)}
                  onChange={(e) => handleStatusChange('is_enriched', e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-vibe-500"
                >
                  <option value="">Any</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
