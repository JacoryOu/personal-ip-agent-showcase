/**
 * Creation History & Draft Archive Storage Service
 * Supports offline-first LocalStorage persistence with resilient backend synchronization.
 */
import { API_BASE_URL, apiFetch } from './api'

export interface HistoryDraftItem {
  id: string
  topic: string
  content: string
  original_draft?: string
  summary?: string
  blueprint_title?: string
  blueprint_id?: string
  source_material_id?: string
  benchmark_blueprint_id?: string
  lineage_snapshot?: Record<string, any>
  word_count: number
  created_at: string
  updated_at: string
  tags?: string[]
}

const STORAGE_KEY = 'pc_ip_creation_history_v1'

export function getLocalDrafts(): HistoryDraftItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (e) {
    console.error('Failed to load local history drafts:', e)
    return []
  }
}

export function setLocalDrafts(drafts: HistoryDraftItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts))
  } catch (e) {
    console.error('Failed to persist history drafts to localStorage:', e)
  }
}

export async function fetchRemoteDrafts(userId?: string): Promise<HistoryDraftItem[]> {
  try {
    const url = userId
      ? `${API_BASE_URL}/api/drafts?user_id=${encodeURIComponent(userId)}`
      : `${API_BASE_URL}/api/drafts`
    const res = await apiFetch(url)
    if (res.ok) {
      const data = await res.json()
      if (Array.isArray(data)) {
        return data.map((d: any) => ({
          id: String(d.id),
          topic: d.topic || '无标题草稿',
          content: d.user_final_draft || d.original_ai_draft || '',
          original_draft: d.original_ai_draft || '',
          summary: d.metadata_?.summary || d.metadata?.summary || '',
          blueprint_title: d.metadata_?.blueprint_title || d.metadata?.blueprint_title,
          blueprint_id: d.metadata_?.blueprint_id || d.metadata?.blueprint_id,
          source_material_id: d.source_material_id,
          benchmark_blueprint_id: d.benchmark_blueprint_id,
          lineage_snapshot: d.lineage_snapshot,
          word_count: d.content?.length || d.user_final_draft?.length || 0,
          created_at: d.created_at || new Date().toISOString(),
          updated_at: d.updated_at || new Date().toISOString(),
          tags: d.metadata_?.tags || d.metadata?.tags || [],
        }))
      }
    }
  } catch {
    // Graceful offline fallback
  }
  return []
}

export async function getAllHistoryDrafts(userId?: string): Promise<HistoryDraftItem[]> {
  const local = getLocalDrafts()
  try {
    const remote = await fetchRemoteDrafts(userId)
    const map = new Map<string, HistoryDraftItem>()
    for (const item of remote) {
      map.set(item.id, item)
    }
    for (const item of local) {
      if (!map.has(item.id)) {
        map.set(item.id, item)
      } else {
        const existing = map.get(item.id)!
        if (new Date(item.updated_at).getTime() > new Date(existing.updated_at).getTime()) {
          map.set(item.id, item)
        }
      }
    }
    const merged = Array.from(map.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    setLocalDrafts(merged)
    return merged
  } catch {
    return local
  }
}

export async function saveDraftToArchive(
  draft: Omit<HistoryDraftItem, 'id' | 'created_at' | 'updated_at'> & {
    id?: string
    created_at?: string
    updated_at?: string
  }
): Promise<HistoryDraftItem> {
  const id = draft.id || `draft_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`
  const now = new Date().toISOString()
  const fullItem: HistoryDraftItem = {
    id,
    topic: draft.topic || '未命名作品',
    content: draft.content || '',
    original_draft: draft.original_draft || draft.content || '',
    summary: draft.summary || '',
    blueprint_title: draft.blueprint_title,
    blueprint_id: draft.blueprint_id,
    source_material_id: draft.source_material_id,
    benchmark_blueprint_id: draft.benchmark_blueprint_id,
    lineage_snapshot: draft.lineage_snapshot,
    word_count: draft.word_count || draft.content?.length || 0,
    created_at: draft.created_at || now,
    updated_at: now,
    tags: draft.tags || [],
  }

  const local = getLocalDrafts()
  const existingIdx = local.findIndex((d) => d.id === id)
  if (existingIdx >= 0) {
    local[existingIdx] = fullItem
  } else {
    local.unshift(fullItem)
  }
  setLocalDrafts(local)

  try {
    await apiFetch(`${API_BASE_URL}/api/drafts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: fullItem.id,
        topic: fullItem.topic,
        original_ai_draft: fullItem.original_draft,
        user_final_draft: fullItem.content,
        source_material_id: fullItem.source_material_id,
        benchmark_blueprint_id: fullItem.benchmark_blueprint_id,
        lineage_snapshot: fullItem.lineage_snapshot,
        metadata_: {
          summary: fullItem.summary,
          blueprint_title: fullItem.blueprint_title,
          blueprint_id: fullItem.blueprint_id,
          tags: fullItem.tags,
        },
      }),
    })
  } catch {
    // offline fallback
  }

  return fullItem
}

export async function deleteDraftFromArchive(id: string): Promise<void> {
  const local = getLocalDrafts().filter((d) => d.id !== id)
  setLocalDrafts(local)

  try {
    await apiFetch(`${API_BASE_URL}/api/drafts/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
  } catch {
    // ignore
  }
}

export function clearAllLocalDrafts(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function exportHistoryAsJson(drafts: HistoryDraftItem[]): void {
  const blob = new Blob([JSON.stringify(drafts, null, 2)], { type: 'application/json' })
  const dlAnchor = document.createElement('a')
  dlAnchor.href = URL.createObjectURL(blob)
  dlAnchor.download = `creation_history_backup_${new Date().toISOString().slice(0, 10)}.json`
  dlAnchor.click()
  dlAnchor.remove()
}

export function importHistoryFromJson(jsonStr: string): number {
  try {
    const parsed = JSON.parse(jsonStr)
    if (!Array.isArray(parsed)) return 0
    const local = getLocalDrafts()
    const map = new Map<string, HistoryDraftItem>()
    for (const item of local) {
      map.set(item.id, item)
    }
    let addedCount = 0
    for (const item of parsed) {
      if (item && item.topic && item.content) {
        const id = item.id || `imported_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
        if (!map.has(id)) {
          addedCount++
        }
        map.set(id, {
          id,
          topic: item.topic,
          content: item.content,
          original_draft: item.original_draft || item.content,
          summary: item.summary || '',
          blueprint_title: item.blueprint_title,
          blueprint_id: item.blueprint_id,
          source_material_id: item.source_material_id,
          benchmark_blueprint_id: item.benchmark_blueprint_id,
          lineage_snapshot: item.lineage_snapshot,
          word_count: item.word_count || item.content.length,
          created_at: item.created_at || new Date().toISOString(),
          updated_at: item.updated_at || new Date().toISOString(),
          tags: item.tags || [],
        })
      }
    }
    const result = Array.from(map.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    setLocalDrafts(result)
    return addedCount
  } catch (e) {
    console.error('Failed to import JSON history:', e)
    throw new Error('JSON 数据格式无效，请上传正确的作品归档备份文件。')
  }
}
