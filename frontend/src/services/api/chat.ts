import { apiFetch, API_BASE_URL } from './client'

// ---------------------------------------------------------------------------
// Cognitive Chat Lounge APIs (Phase 2)
// ---------------------------------------------------------------------------

export interface DNACapsule {
  type: 'story' | 'dna' | 'timeline_pin' | 'evolution'
  title: string
  summary: string
  occurred_at?: string | null
}

export interface ChatMessageRequest {
  message: string
  mode?: 'free_talk' | 'coach_inquiry' | 'timeline_review' | 'interview' | string
  session_id?: string
  user_id?: string
}

export interface ChatMessageResponse {
  reply: string
  session_id: string
  capsules: DNACapsule[]
}

export interface ChatSessionHistoryMessage {
  role: string
  content: string
  ts: string
}

export interface ChatHistoryResponse {
  session_id: string
  messages: ChatSessionHistoryMessage[]
}

export interface ChatSessionItem {
  session_id: string
  user_id?: string
  created_at: string
  mode: string
  message_count: number
  first_message?: string
}

export async function sendLoungeMessage(
  payload: ChatMessageRequest
): Promise<ChatMessageResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/chat/lounge/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to send lounge message')
  }
  return response.json()
}

export async function fetchLoungeHistory(sessionId: string): Promise<ChatHistoryResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/chat/lounge/history?session_id=${encodeURIComponent(sessionId)}`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch lounge history')
  }
  return response.json()
}

export async function fetchLoungeSessions(): Promise<ChatSessionItem[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/chat/lounge/sessions`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch lounge sessions')
  }
  return response.json()
}

export async function deleteLoungeSession(sessionId: string) {
  const res = await apiFetch(`${API_BASE_URL}/api/chat/lounge/sessions/${sessionId}`, {
    method: 'DELETE'
  })
  if (!res.ok) throw new Error('Failed to delete session')
  return res.json()
}

export async function renameLoungeSession(sessionId: string, title: string) {
  const res = await apiFetch(`${API_BASE_URL}/api/chat/lounge/sessions/${sessionId}/title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
  if (!res.ok) throw new Error('Failed to rename session')
  return res.json()
}
