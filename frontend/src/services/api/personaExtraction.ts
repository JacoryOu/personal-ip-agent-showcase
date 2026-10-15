import { apiFetch, API_BASE_URL } from './client'
import type { IPPersona } from './productVault'
import type { EpisodicStoryItem } from './timeline'

// ---------------------------------------------------------------------------
// IP Persona Reverse Extraction & Soul Interview Crystallization
// ---------------------------------------------------------------------------

export interface ExtractedPersonaResult {
  persona: IPPersona
  stories?: EpisodicStoryItem[]
  saved?: boolean
  message?: string
}

export interface CrystallizePersonaResponse {
  persona: IPPersona
  stories?: EpisodicStoryItem[]
  session_id?: string
  message?: string
}

export async function extractPersonaFromText(
  text: string,
  autoSave?: boolean
): Promise<ExtractedPersonaResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/personas/extract-from-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      auto_save: autoSave ?? false,
      autoSave: autoSave ?? false,
    }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to extract persona from text')
  }
  return response.json()
}

export async function crystallizePersonaFromSession(
  sessionId: string
): Promise<CrystallizePersonaResponse> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/chat/lounge/sessions/${encodeURIComponent(sessionId)}/crystallize-persona`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }
  )
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to crystallize persona from session')
  }
  return response.json()
}
