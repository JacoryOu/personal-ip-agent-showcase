import { apiFetch, API_BASE_URL } from './client'
import type { EpisodicStoryItem } from './timeline'
import type { IPPersona } from './productVault'
import type { ProductVaultItem } from './productVault'

// Connection testing types and helper
export interface OutlineSection {
  title: string
  bullet_points: string[]
}

export interface Outline {
  title: string
  rationale: string
  sections: OutlineSection[]
}

export interface OutlineOutput {
  outline_a: Outline
  outline_b: Outline
}

export interface ViewpointOption {
  key: string
  label: string
  text: string
}

export interface CoreViewpoint {
  id: string
  claim: string
  section_title?: string
  options: ViewpointOption[]
}

export interface ViewpointJudgment {
  viewpoint_id: string
  claim: string
  selected_key: string
  selected_text: string
  custom_note?: string
}

export interface DraftOutput {
  id?: string
  draft_id?: string
  title: string
  summary?: string
  content: string
  word_count?: number
  core_viewpoints?: CoreViewpoint[]
  injected_dna?: any
  source_material_id?: string
  benchmark_blueprint_id?: string
  lineage_snapshot?: Record<string, any>
  persona_id?: string
  persona?: IPPersona
  product_id?: string
  product?: ProductVaultItem
  story_ids?: string[]
  stories?: EpisodicStoryItem[]
}

export async function generateOutlines(
  topic: string,
  additionalContext?: string,
  personaId?: string,
  productId?: string,
  storyIds?: string[]
): Promise<OutlineOutput> {
  const response = await apiFetch(`${API_BASE_URL}/api/outlines/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic: topic.trim(),
      additional_context: additionalContext?.trim() || undefined,
      persona_id: personaId || undefined,
      product_id: productId || undefined,
      story_ids: storyIds && storyIds.length > 0 ? storyIds : undefined,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Request failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}

export async function generateDraft(
  topic: string,
  outline: Outline,
  additionalContext?: string,
  sourceMaterialId?: string,
  benchmarkBlueprintId?: string,
  personaId?: string,
  productId?: string,
  storyIds?: string[]
): Promise<DraftOutput> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic: topic.trim(),
      outline,
      additional_context: additionalContext?.trim() || undefined,
      source_material_id: sourceMaterialId,
      benchmark_blueprint_id: benchmarkBlueprintId,
      persona_id: personaId || undefined,
      product_id: productId || undefined,
      story_ids: storyIds && storyIds.length > 0 ? storyIds : undefined,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Request failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}
