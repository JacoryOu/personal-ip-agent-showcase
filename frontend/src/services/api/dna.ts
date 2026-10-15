import { apiFetch, API_BASE_URL } from './client'
import type { ViewpointJudgment } from './drafting'

export interface ThinkingDNA {
  vocabulary_habits: string[]
  logic_preferences: string[]
  core_values: string[]
  summary?: string
}

export interface DNAExtractionOutput {
  has_diff: boolean
  diff_summary?: string
  thinking_dna?: ThinkingDNA
  draft_id?: string
  dna_record_id?: string
}

export interface DiffInput {
  original_ai_draft: string
  user_final_draft: string
  topic?: string
  draft_id?: string
  user_id?: string
  viewpoint_judgments?: ViewpointJudgment[]
}

export async function extractThinkingDNA(
  payload: DiffInput
): Promise<DNAExtractionOutput> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/extract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg =
      errorData.detail ||
      errorData.message ||
      `Request failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}

export async function getDNARecords(): Promise<any[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/records`)
  if (!response.ok) {
    throw new Error(`Failed to fetch DNA records with status ${response.status}`)
  }
  return response.json()
}

export type CognitiveDimension = 'vocabulary' | 'logic_preference' | 'core_value' | 'viewpoint_stance'
export type TraitStatus = 'active' | 'pinned' | 'suppressed'

export interface CognitiveTrait {
  id: string
  dimension: CognitiveDimension
  statement: string
  confidence_score: number
  status: TraitStatus
  source_draft_id?: string
  evolution_boost_count?: number
  last_boosted_at?: string
  created_at: string
  updated_at: string
}

export interface CognitiveProfile {
  user_id: string
  traits: CognitiveTrait[]
}

export async function fetchCognitiveProfile(userId?: string): Promise<CognitiveProfile> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/profile?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/profile`
  const response = await apiFetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch cognitive profile: ${response.status}`)
  }
  return response.json()
}

export async function pinTrait(traitId: string, userId?: string): Promise<CognitiveTrait> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/traits/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trait_id: traitId, user_id: userId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to pin trait: ${response.status}`)
  }
  return response.json()
}

export async function unpinTrait(traitId: string, userId?: string): Promise<CognitiveTrait> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/traits/unpin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trait_id: traitId, user_id: userId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to unpin trait: ${response.status}`)
  }
  return response.json()
}

export async function suppressTrait(traitId: string, userId?: string): Promise<CognitiveTrait> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/traits/suppress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trait_id: traitId, user_id: userId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to suppress trait: ${response.status}`)
  }
  return response.json()
}

export async function addTrait(
  dimension: CognitiveDimension,
  statement: string,
  userId?: string
): Promise<CognitiveTrait> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/traits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dimension, statement, user_id: userId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add trait: ${response.status}`)
  }
  return response.json()
}

export async function deleteTrait(
  traitId: string,
  userId?: string
): Promise<{ success: boolean; message: string }> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/traits/${traitId}?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/traits/${traitId}`
  const response = await apiFetch(url, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error(`Failed to delete trait: ${response.status}`)
  }
  return response.json()
}

export async function supersedeTrait(payload: {
  old_trait_id: string
  new_content: string
  evolution_reason: string
  user_id?: string
}): Promise<any> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/supersede`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to supersede trait')
  }
  return response.json()
}
