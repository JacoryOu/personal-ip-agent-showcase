import { apiFetch, API_BASE_URL } from './client'
import type { BenchmarkBlueprint } from './benchmarks'
import type { DraftOutput } from './drafting'
import type { ThinkingDNA } from './dna'

export interface XhsCard {
  card_type: 'cover' | 'point' | 'summary'
  index?: string
  badge?: string
  title?: string
  subtitle?: string
  tags?: string[]
  author?: string
  hook?: string
  image_prompt?: string
  suggested_prompt?: string
  step_number?: string
  key_points?: string[]
  pain_point_analysis?: string
  highlight?: string
  golden_quote?: string
  checklist?: string[]
  interaction_prompt?: string
  cta?: string
}

export interface WechatCoverImage {
  title: string
  subtitle: string
  badge: string
  author: string
  ratio: string
}

export interface WechatQuoteCard {
  quote: string
  source: string
  author: string
  ratio: string
}

export interface WechatImagePrompt {
  role: string
  prompt_zh: string
  prompt_en: string
}

export interface WechatSectionIllustration {
  id?: string
  section_title: string
  section_index?: number
  anchor?: string
  caption: string
  prompt: string
  prompt_zh?: string
  prompt_en?: string
  image_url?: string
}

export interface DistributedPlatform {
  title?: string
  content: string
  tags?: string[]
  cover?: XhsCard
  body_cards?: XhsCard[]
  summary_card?: XhsCard
  cards?: XhsCard[]
  cover_image?: WechatCoverImage
  quote_card?: WechatQuoteCard
  image_prompts?: WechatImagePrompt[]
  section_illustrations?: WechatSectionIllustration[]
  thread?: string[]
  hook?: string
  estimated_duration_seconds?: number
}

export interface DistributionResult {
  success: boolean
  title: string
  platforms: {
    xiaohongshu?: DistributedPlatform
    wechat?: DistributedPlatform
    twitter?: DistributedPlatform
    video?: DistributedPlatform
  }
}

export interface BlueprintDraftPayload {
  topic: string
  blueprint_id?: string
  blueprint?: Partial<BenchmarkBlueprint> | any
  additional_context?: string
  user_id?: string
  thinking_dna?: ThinkingDNA
  source_material_id?: string
  persona_id?: string
  product_id?: string
  story_ids?: string[]
}

export async function generateDraftFromBlueprint(
  payload: BlueprintDraftPayload
): Promise<DraftOutput> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/generate-from-blueprint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic: payload.topic.trim(),
      blueprint_id: payload.blueprint_id,
      blueprint: payload.blueprint,
      additional_context: payload.additional_context?.trim() || undefined,
      user_id: payload.user_id,
      thinking_dna: payload.thinking_dna,
      source_material_id: payload.source_material_id,
      persona_id: payload.persona_id,
      product_id: payload.product_id,
      story_ids: payload.story_ids,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Request failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}

export async function generateBlueprintDraft(
  payloadOrTopic: BlueprintDraftPayload | string,
  blueprintId?: string,
  additionalContext?: string,
  personaId?: string,
  productId?: string,
  storyIds?: string[]
): Promise<DraftOutput> {
  if (typeof payloadOrTopic === 'string') {
    return generateDraftFromBlueprint({
      topic: payloadOrTopic,
      blueprint_id: blueprintId,
      additional_context: additionalContext,
      persona_id: personaId,
      product_id: productId,
      story_ids: storyIds,
    })
  }
  return generateDraftFromBlueprint(payloadOrTopic)
}

export async function distributeContent(payload: {
  content: string
  title?: string
  platforms?: string[]
}): Promise<DistributionResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/distribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Distribution failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}

export async function distributeDraftById(
  draftId: string,
  platforms?: string[]
): Promise<DistributionResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/${encodeURIComponent(draftId)}/distribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platforms }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Distribution failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}
