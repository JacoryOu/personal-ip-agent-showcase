import { getModelHeaders } from '../modelSettings'

export interface ConnectionTestPayload {
  api_key?: string
  base_url?: string
  model?: string
  is_system_default?: boolean
}

export interface ConnectionTestResult {
  success: boolean
  latency_ms: number
  model: string
  message: string
}


/**
 * Identity for the local MVP API.
 *
 * The backend accepts either "Authorization: Bearer <secret>" or "X-API-Key".
 * Resolution order, most specific first:
 *   1. a value set at runtime via setApiKey() (kept in sessionStorage only),
 *   2. VITE_API_KEY from the dev environment file.
 *
 * VITE_API_KEY is inlined into the production bundle by Vite, so it must stay
 * empty in production. It exists so a local single-user dev server can talk to
 * a backend started with AUTH_REQUIRED=true. This is a local identity layer,
 * not an enterprise IAM: the key is a shared static secret with no per-user
 * identity, rotation or revocation beyond restarting the backend.
 */
const API_KEY_STORAGE_KEY = 'cog.api_key'

export function setApiKey(value: string | null): void {
  try {
    if (value) {
      window.sessionStorage.setItem(API_KEY_STORAGE_KEY, value)
    } else {
      window.sessionStorage.removeItem(API_KEY_STORAGE_KEY)
    }
  } catch {
    // Private-mode browsers can refuse sessionStorage; the env key still works.
  }
}

export function getApiKey(): string {
  try {
    const stored = window.sessionStorage.getItem(API_KEY_STORAGE_KEY)
    if (stored) return stored
  } catch {
    // ignore and fall through
  }
  return import.meta.env.VITE_API_KEY || ''
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  const modelHeaders = getModelHeaders()
  for (const [k, v] of Object.entries(modelHeaders)) {
    if (v && !headers.has(k)) {
      headers.set(k, v)
    }
  }
  const apiKey = getApiKey()
  if (apiKey && !headers.has('Authorization') && !headers.has('X-API-Key')) {
    headers.set('X-API-Key', apiKey)
  }
  return window.fetch(input, {
    ...init,
    headers,
  })
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8083'
