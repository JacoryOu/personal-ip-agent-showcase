import { apiFetch, API_BASE_URL } from './client'
import type { ThinkingDNA } from './dna'

export interface BenchmarkBlueprint {
  id: string
  title: string
  source_url?: string
  hook_style: string
  structural_stages: string[]
  emotional_arc: string
  pacing: string
  word_count: number
  clash_points_count: number
  created_at: string
}

export interface ViewpointClashPoint {
  claim: string
  context: string
  suggested_critique_angle: string
}

export interface BenchmarkDeconstructionResult {
  success: boolean
  blueprint: BenchmarkBlueprint
  clash_points: ViewpointClashPoint[]
  message: string
}

export interface SkillInfo {
  name: string
  description: string
  runner_mode: string
  permissions: string[]
  parameters: any
  entrypoint: string
}

export interface OwnWorkIngestResult {
  success: boolean
  dna_record_id: string
  user_id: string
  summary: string
  extracted_dna: ThinkingDNA
  mem0_actions: {
    ADD: Array<{ dimension: string; statement: string; id: string }>
    UPDATE: Array<{ dimension: string; statement: string; id: string }>
    NOOP: Array<{ dimension: string; statement: string; id: string }>
  }
  total_traits_count: number
}

export async function ingestOwnWork(payload: {
  content?: string
  url?: string
  title?: string
  user_id?: string
}): Promise<OwnWorkIngestResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/ingest-own-work`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to ingest own work: ${response.status}`)
  }
  return response.json()
}

export async function deconstructBenchmark(payload: {
  content?: string
  url?: string
  title?: string
  user_id?: string
}): Promise<BenchmarkDeconstructionResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/deconstruct-benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to deconstruct benchmark: ${response.status}`)
  }
  return response.json()
}

export async function recordDialogueClash(payload: {
  messages: Array<{ role: string; content: string }>
  debate_topic?: string
  user_id?: string
}): Promise<any> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/dialogue-clash`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to record dialogue clash: ${response.status}`)
  }
  return response.json()
}

export async function fetchBenchmarkBlueprints(userId?: string): Promise<BenchmarkBlueprint[]> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/benchmarks?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/benchmarks`
  const response = await apiFetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch benchmark blueprints: ${response.status}`)
  }
  return response.json()
}

export async function fetchActiveSkills(): Promise<SkillInfo[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/skills`)
  if (!response.ok) {
    throw new Error(`Failed to fetch active skills: ${response.status}`)
  }
  return response.json()
}
