import { apiFetch, API_BASE_URL } from './client'

// ==============================================================================
// Phase 4: Audience Feedback Ingestion & Cognitive Asset Evolution
// ==============================================================================

export interface BoostedTrait {
  id: string
  statement: string
  dimension: string
  old_confidence: number
  new_confidence: number
  boost_amount: number
  reason?: string
}

export interface FeedbackExtractResult {
  feedback_id: string
  draft_id: string
  resonant_ideas: string[]
  controversy_points: string[]
  inspiration_notes: string[]
  created_materials: Array<{
    id: string
    title: string
    cleaned_content: string
    material_type: string
    tags: string[]
  }>
  boosted_traits: BoostedTrait[]
  evolution_summary: string
}

export interface DraftFeedbackItem {
  id: string
  draft_id: string
  user_id: string
  comments_text: string
  metrics: Record<string, any>
  extracted_insights?: {
    resonant_ideas?: string[]
    controversy_points?: string[]
    inspiration_notes?: string[]
    evolution_summary?: string
  }
  boosted_dna_traits?: Array<{
    id: string
    statement: string
    dimension: string
    old_confidence: number
    new_confidence: number
    boost_amount: number
    reason?: string
  }>
  saved_material_ids?: string[]
  created_at?: string
  updated_at?: string
}

export async function recordDraftFeedback(
  draftId: string,
  commentsText: string,
  metrics?: Record<string, any>,
  userId?: string
): Promise<DraftFeedbackItem> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/${encodeURIComponent(draftId)}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      comments_text: commentsText,
      metrics: metrics || {},
      user_id: userId,
    }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to record draft feedback')
  }
  return response.json()
}

export async function extractDraftFeedbackInsights(
  draftId: string,
  payload: {
    comments_text?: string
    feedback_id?: string
    metrics?: Record<string, any>
    user_id?: string
  }
): Promise<FeedbackExtractResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/${encodeURIComponent(draftId)}/feedback/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to extract feedback insights')
  }
  return response.json()
}

export async function fetchDraftFeedbacks(draftId: string): Promise<DraftFeedbackItem[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/${encodeURIComponent(draftId)}/feedback`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch draft feedbacks')
  }
  return response.json()
}
