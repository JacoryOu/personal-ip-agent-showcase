import { apiFetch, API_BASE_URL } from './client'

export interface Material {
  id: string
  user_id: string
  material_type: 'trending' | 'benchmark' | 'personal' | string
  source_platform?: string
  source_url?: string
  source_author?: string
  title: string
  raw_content?: string
  cleaned_content: string
  blueprint_data?: any
  tags: string[]
  status: 'inbox' | 'archived' | 'used' | 'discarded' | string
  meta_info: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface DraftLineage {
  draft_id: string
  topic: string
  title: string
  source_material_id?: string
  source_material?: Partial<Material> | null
  benchmark_blueprint_id?: string
  benchmark_blueprint?: any
  thinking_dna_used?: any
  lineage_snapshot: Record<string, any>
  created_at?: string
  updated_at?: string
}

// Material Vault & Lineage API Endpoints
// ==========================================

export async function fetchMaterials(params?: {
  material_type?: string
  status?: string
  tag?: string
  search?: string
  user_id?: string
  limit?: number
  offset?: number
}): Promise<Material[]> {
  const query = new URLSearchParams()
  if (params?.material_type) query.set('material_type', params.material_type)
  if (params?.status) query.set('status', params.status)
  if (params?.tag) query.set('tag', params.tag)
  if (params?.search) query.set('search', params.search)
  if (params?.user_id) query.set('user_id', params.user_id)
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))

  const url = `${API_BASE_URL}/api/materials${query.toString() ? `?${query.toString()}` : ''}`
  const response = await apiFetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch materials: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchMaterial(id: string): Promise<Material> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials/${id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch material: ${response.statusText}`)
  }
  return response.json()
}

export async function createMaterial(payload: Partial<Material>): Promise<Material> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to create material')
  }
  return response.json()
}

export async function collectUrl(payload: {
  url: string
  extract_blueprint?: boolean
  user_id?: string
  tags?: string[]
  title?: string
  save?: boolean
}): Promise<{ success: boolean; material?: Material; blueprint?: any; preview?: any }> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials/collect-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to collect URL')
  }
  return response.json()
}

export async function fetchTrending(payload?: {
  platform?: string
  limit?: number
  batch_save?: boolean
  user_id?: string
}): Promise<{ success: boolean; count: number; platform: string; items: Material[] }> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials/fetch-trending`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch trending radar')
  }
  return response.json()
}

export async function updateMaterial(id: string, payload: Partial<Material>): Promise<Material> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to update material')
  }
  return response.json()
}

export async function deleteMaterial(id: string): Promise<{ success: boolean; id: string }> {
  const response = await apiFetch(`${API_BASE_URL}/api/materials/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete material: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchDraftLineage(draftId: string): Promise<DraftLineage> {
  const response = await apiFetch(`${API_BASE_URL}/api/drafts/${draftId}/lineage`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch draft lineage')
  }
  return response.json()
}
