import { apiFetch, API_BASE_URL } from './client'

export type MomentCategory = '专业沉淀' | '生活切片' | '好物自用' | '互动截流' | '岁月反思'
export type TimeNarrativeMode = 'invisible' | 'fuzzy' | 'solar_term' | 'anniversary'
export type TriggerType = 'study_insight' | 'reading_notes' | 'case_experience' | 'daily_thought'
export type LengthTier = 'short' | 'standard' | 'deep'

export interface GenerateMomentRequest {
  category: MomentCategory
  topic?: string
  product_id?: string
  persona_id?: string
  time_narrative_mode?: TimeNarrativeMode
  user_id?: string
  trigger_type?: TriggerType
  raw_experience?: string
  my_takeaway?: string
  length_tier?: LengthTier
}

export interface GenerateMomentResponse {
  text: string
  estimated_lines: number
  will_fold: boolean
  fold_preview: string
  pinned_comment: string
  visual_card_prompt: string
  tags: string[]
  character_count?: number
}

export interface GenerateCommunityRequest {
  script_type?: 'discussion_starter' | 'sale_theater' | 'qa_spark'
  topic?: string
  product_id?: string
  persona_id?: string
  user_id?: string
}

export interface GenerateCommunityResponse {
  content: string
  script_type: string
  roles: string[]
  recommended_timing: string
  call_to_action: string
}

export interface PrivateDomainTemplate {
  category: string
  name: string
  description: string
  example_topic: string
  sample_hook: string
  recommended_timing: string
  target_goal: string
}

export async function generateMoment(
  payload: GenerateMomentRequest
): Promise<GenerateMomentResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/private-domain/generate-moment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to generate WeChat Moment')
  }
  return response.json()
}

export async function generateCommunity(
  payload: GenerateCommunityRequest
): Promise<GenerateCommunityResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/private-domain/generate-community`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to generate community script')
  }
  return response.json()
}

export async function fetchPrivateDomainTemplates(): Promise<PrivateDomainTemplate[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/private-domain/templates`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch templates')
  }
  return response.json()
}
