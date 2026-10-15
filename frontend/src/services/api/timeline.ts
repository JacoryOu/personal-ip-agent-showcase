import { apiFetch, API_BASE_URL } from './client'

// ---------------------------------------------------------------------------
// Timeline & Stories APIs (Phase 1 & Phase 4)
// ---------------------------------------------------------------------------

export interface EpisodicStoryItem {
  id: string
  user_id?: string
  title: string
  story_content: string
  story_type: string
  occurred_at: string
  tags: string[]
  confidence_score: number
  created_at?: string
}

export interface TimelineEventItem {
  type: 'story' | 'dna_evolution'
  occurred_at?: string | null
  title: string
  summary?: string
  story_type?: string
  evolution_reason?: string
  version?: number
  trait_status?: string
  id: string
}

export async function fetchStories(userId?: string): Promise<EpisodicStoryItem[]> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/v2/stories?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/v2/stories`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch stories')
  }
  return response.json()
}

export async function createStory(data: Partial<EpisodicStoryItem>): Promise<EpisodicStoryItem> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/stories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to create story')
  }
  return response.json()
}

export async function fetchTimeline(userId?: string): Promise<TimelineEventItem[]> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/v2/timeline?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/v2/timeline`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch timeline')
  }
  return response.json()
}
