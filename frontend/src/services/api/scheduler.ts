import { apiFetch, API_BASE_URL } from './client'
import type { Material } from './materials'

// ==============================================================================
// Dual-Wheel Inspection Scheduler & Daily Briefing
// ==============================================================================

export interface SchedulerSettings {
  enabled: boolean
  interval_hours: number
  daily_briefing_time: string
  wheel1_enabled: boolean
  wheel2_enabled: boolean
  interest_tags: string[]
  viral_threshold_likes: number
  max_trending_per_run: number
  max_posts_per_account: number
  notify_unread: boolean
}

export interface SchedulerStatus {
  running: boolean
  enabled: boolean
  interval_hours: number
  daily_briefing_time: string
  next_run_time?: string
  last_run_time?: string
  last_execution_summary?: {
    success: boolean
    wheel1_new_topics: number
    wheel2_new_blueprints: number
    total_new_items: number
    duration_ms: number
    message: string
    executed_at?: string
  }
  settings: SchedulerSettings
  unread_briefing_count: number
}

export interface SchedulerTriggerResult {
  success: boolean
  message: string
  wheel1_new_topics: number
  wheel2_new_blueprints: number
  total_new_items: number
  duration_ms: number
  summary: Record<string, any>
}

export interface DailyBriefingData {
  date: string
  generated_at: string
  unread: boolean
  total_items: number
  trending_count: number
  benchmark_count: number
  trending_topics: Material[]
  benchmark_blueprints: Material[]
}

export async function fetchSchedulerStatus(userId?: string): Promise<SchedulerStatus> {
  const url = userId
    ? `${API_BASE_URL}/api/scheduler/status?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/scheduler/status`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch scheduler status')
  }
  return response.json()
}

export async function triggerInspection(userId?: string): Promise<SchedulerTriggerResult> {
  const url = userId
    ? `${API_BASE_URL}/api/scheduler/trigger?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/scheduler/trigger`
  const response = await apiFetch(url, { method: 'POST' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to trigger inspection')
  }
  return response.json()
}

export async function updateSchedulerSettings(
  payload: Partial<SchedulerSettings>
): Promise<SchedulerSettings> {
  const response = await apiFetch(`${API_BASE_URL}/api/scheduler/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to update scheduler settings')
  }
  return response.json()
}

export async function fetchTodayBriefing(userId?: string): Promise<DailyBriefingData> {
  const url = userId
    ? `${API_BASE_URL}/api/scheduler/briefing/today?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/scheduler/briefing/today`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch today briefing')
  }
  return response.json()
}

export async function markBriefingAsRead(date?: string): Promise<{ success: boolean; marked_date: string }> {
  const url = date
    ? `${API_BASE_URL}/api/scheduler/briefing/mark-read?date=${encodeURIComponent(date)}`
    : `${API_BASE_URL}/api/scheduler/briefing/mark-read`
  const response = await apiFetch(url, { method: 'POST' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to mark briefing as read')
  }
  return response.json()
}

export async function confirmBriefingIntoVault(userId?: string): Promise<{ success: boolean; count: number; message: string }> {
  const url = userId
    ? `${API_BASE_URL}/api/scheduler/briefing/confirm?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/scheduler/briefing/confirm`
  const response = await apiFetch(url, { method: 'POST' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to confirm briefing into vault')
  }
  return response.json()
}
