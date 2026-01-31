'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { TrackList } from '@/components/TrackList'
import { SearchBar } from '@/components/SearchBar'
import { FilterPanel } from '@/components/FilterPanel'
import { api } from '@/lib/api'
import type { TrackListResponse, TrackSearchParams } from '@/lib/types'

export default function LibraryPage() {
  const [searchParams, setSearchParams] = useState<TrackSearchParams>({
    page: 1,
    page_size: 50,
    sort_by: 'title',
    sort_order: 'asc',
  })

  const { data, isLoading, error } = useQuery<TrackListResponse>({
    queryKey: ['tracks', searchParams],
    queryFn: () => api.getTracks(searchParams),
  })

  const handleSearch = (query: string) => {
    setSearchParams((prev) => ({ ...prev, query, page: 1 }))
  }

  const handleFilterChange = (filters: Partial<TrackSearchParams>) => {
    setSearchParams((prev) => ({ ...prev, ...filters, page: 1 }))
  }

  const handlePageChange = (page: number) => {
    setSearchParams((prev) => ({ ...prev, page }))
  }

  const handleSort = (sort_by: string) => {
    setSearchParams((prev) => ({
      ...prev,
      sort_by,
      sort_order: prev.sort_by === sort_by && prev.sort_order === 'asc' ? 'desc' : 'asc',
    }))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Library</h1>
          <p className="text-gray-400 mt-1">
            {data?.total ?? 0} tracks in your collection
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button className="px-4 py-2 bg-vibe-600 hover:bg-vibe-700 rounded-lg transition-colors">
            Import Tracks
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <SearchBar onSearch={handleSearch} />
        </div>
        <FilterPanel onFilterChange={handleFilterChange} filters={searchParams} />
      </div>

      {/* Track List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex gap-1">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="w-2 h-8 bg-vibe-500 rounded animate-pulse"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        </div>
      ) : error ? (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
          Error loading tracks. Please try again.
        </div>
      ) : data ? (
        <>
          <TrackList
            tracks={data.items}
            sortBy={searchParams.sort_by}
            sortOrder={searchParams.sort_order}
            onSort={handleSort}
          />

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => handlePageChange(data.page - 1)}
                disabled={data.page <= 1}
                className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-gray-400">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                onClick={() => handlePageChange(data.page + 1)}
                disabled={data.page >= data.total_pages}
                className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
