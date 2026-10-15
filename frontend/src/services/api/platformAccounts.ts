import { apiFetch, API_BASE_URL } from './client'

// Platform Authorization & Benchmark Accounts Ingestion
// ========================================================

export interface PlatformCredential {
  id: string
  user_id: string
  platform: 'wechat' | 'xhs' | 'zhihu' | string
  account_identifier?: string
  status: 'active' | 'expired' | 'pending_login' | 'invalid' | string
  has_cookies: boolean
  cookie_keys: string[]
  last_checked_at?: string
  expires_at?: string
  meta_info?: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface QRLoginStartResult {
  session_key: string
  platform: string
  qr_code_data: string
  expires_in: number
  instructions: string
}

export interface QRLoginStatusResult {
  session_key: string
  platform: string
  status: 'pending_login' | 'scanned' | 'confirmed' | 'expired' | string
  message: string
  credential?: PlatformCredential | null
}

export interface BenchmarkAccount {
  id: string
  user_id: string
  platform: 'wechat' | 'xhs' | 'zhihu' | string
  account_name: string
  account_id: string
  home_url?: string
  avatar_url?: string
  bio?: string
  follower_count?: number
  notes_count?: number
  last_synced_at?: string
  status: 'active' | 'paused' | string
  meta_info?: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface FeedItem {
  id: string
  title: string
  url: string
  author: string
  platform: string
  content: string
  summary: string
  cover_url?: string
  publish_time: string
  likes: number
  collects: number
  comments: number
  shares: number
  hot_score: number
  tags: string[]
  is_ingested?: boolean
}

export interface AccountFeedResult {
  account: BenchmarkAccount
  items: FeedItem[]
  sort_by: string
  total: number
  has_active_credential?: boolean
}

export interface BatchIngestResult {
  success: boolean
  count: number
  material_ids: string[]
  materials: Array<{
    id: string
    title: string
    source_platform: string
    source_author: string
    source_url?: string
    blueprint_data?: any
  }>
}

export async function startPlatformQrLogin(platform: string, userId?: string): Promise<QRLoginStartResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/credentials/qr/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform, user_id: userId }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to start QR login')
  }
  return response.json()
}

export async function checkPlatformQrStatus(sessionKey: string): Promise<QRLoginStatusResult> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/platforms/credentials/qr/status?session_key=${encodeURIComponent(sessionKey)}`
  )
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to check QR login status')
  }
  return response.json()
}

export async function simulateConfirmPlatformQr(
  sessionKey: string,
  accountIdentifier?: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/credentials/qr/simulate-confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_key: sessionKey, account_identifier: accountIdentifier }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to simulate QR confirmation')
  }
  return response.json()
}

export async function saveManualCookies(payload: {
  platform: string
  cookies: any
  account_identifier?: string
  user_id?: string
}): Promise<PlatformCredential> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/credentials/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to save cookies')
  }
  return response.json()
}

export async function fetchPlatformCredentials(userId?: string): Promise<PlatformCredential[]> {
  const url = userId
    ? `${API_BASE_URL}/api/platforms/credentials?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/platforms/credentials`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch credentials')
  }
  return response.json()
}

export async function checkPlatformCredentialValidity(
  platform: string,
  userId?: string
): Promise<{ platform: string; status: string; valid: boolean; message: string; account_identifier?: string }> {
  const url = userId
    ? `${API_BASE_URL}/api/platforms/credentials/${encodeURIComponent(platform)}/check?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/platforms/credentials/${encodeURIComponent(platform)}/check`
  const response = await apiFetch(url, { method: 'POST' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to check credential validity')
  }
  return response.json()
}

export async function deletePlatformCredential(credentialId: string): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/credentials/${encodeURIComponent(credentialId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to delete credential')
  }
  return response.json()
}

export async function fetchBenchmarkAccounts(
  platform?: string,
  userId?: string
): Promise<BenchmarkAccount[]> {
  const query = new URLSearchParams()
  if (platform && platform !== 'all') query.set('platform', platform)
  if (userId) query.set('user_id', userId)

  const url = `${API_BASE_URL}/api/platforms/accounts${query.toString() ? `?${query.toString()}` : ''}`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch benchmark accounts')
  }
  return response.json()
}

export async function createBenchmarkAccount(payload: {
  platform: string
  account_name: string
  account_id?: string
  home_url?: string
  avatar_url?: string
  bio?: string
  user_id?: string
}): Promise<BenchmarkAccount> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to add benchmark account')
  }
  return response.json()
}

export async function deleteBenchmarkAccount(accountId: string): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/accounts/${encodeURIComponent(accountId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to delete benchmark account')
  }
  return response.json()
}

export async function fetchAccountFeed(
  accountId: string,
  sortBy: string = 'latest',
  limit: number = 20
): Promise<AccountFeedResult> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/platforms/accounts/${encodeURIComponent(accountId)}/feed?sort_by=${encodeURIComponent(sortBy)}&limit=${limit}`
  )
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch account feed')
  }
  return response.json()
}

export async function batchIngestFeedPosts(payload: {
  items: FeedItem[]
  extract_blueprint?: boolean
  category?: string
  tags?: string[]
  user_id?: string
}): Promise<BatchIngestResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/platforms/batch-ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to batch ingest posts')
  }
  return response.json()
}
