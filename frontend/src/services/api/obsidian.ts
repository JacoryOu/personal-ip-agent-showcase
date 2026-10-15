import { apiFetch, API_BASE_URL } from './client'

export async function fetchObsidianStatus(vaultPath?: string): Promise<any> {
  const url = vaultPath
    ? `${API_BASE_URL}/api/obsidian/status?vault_path=${encodeURIComponent(vaultPath)}`
    : `${API_BASE_URL}/api/obsidian/status`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch obsidian status')
  }
  return response.json()
}

export async function scanObsidianVault(payload: {
  vault_path: string
  target_tags?: string[]
  target_folders?: string[]
}): Promise<any> {
  const response = await apiFetch(`${API_BASE_URL}/api/obsidian/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to scan obsidian vault')
  }
  return response.json()
}
