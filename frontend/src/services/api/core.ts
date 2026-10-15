import { apiFetch, API_BASE_URL } from './client'
import type { ConnectionTestPayload, ConnectionTestResult } from './client'

export interface CurrentServerSettings {
  model: string
  base_url: string
  api_key_configured: boolean
  masked_api_key: string
}

export interface HealthResponse {
  status: string
  message: string
}

export async function testConnection(payload: ConnectionTestPayload): Promise<ConnectionTestResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/settings/test-connection`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function getCurrentServerSettings(): Promise<CurrentServerSettings> {
  const response = await apiFetch(`${API_BASE_URL}/api/settings/current`)
  if (!response.ok) {
    throw new Error(`Failed to fetch current server settings: ${response.status}`)
  }
  return response.json()
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await apiFetch(`${API_BASE_URL}/`)
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return response.json()
}
