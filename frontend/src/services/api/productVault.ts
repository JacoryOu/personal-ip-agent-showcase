import { apiFetch, API_BASE_URL } from './client'

// ===========================================================================
// Phase 1 ~ Phase 4: Personas, Products, Private Domain Hub & Chat Lounge APIs
// ===========================================================================

export interface IPPersona {
  id: string
  user_id?: string
  name: string
  target_audience: string
  tone_style: string
  reader_salutation: string
  origin_story: string
  is_active: boolean
  created_at?: string
}

export interface ProductVaultItem {
  id: string
  user_id?: string
  product_name: string
  category: string
  core_ingredients: string
  suitable_conditions: string
  taboos: string
  personal_usage_experience: string
  conversion_hooks: string
  is_active: boolean
  cover_image?: string
  gallery_images?: string[]
  service_rights_images?: string[]
  created_at?: string
}

export type Product = ProductVaultItem

export async function fetchPersonas(userId?: string): Promise<IPPersona[]> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/v2/personas?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/v2/personas`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch personas')
  }
  return response.json()
}

export async function createPersona(data: Partial<IPPersona>): Promise<IPPersona> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/personas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to create persona')
  }
  return response.json()
}

export async function activatePersona(id: string, isActive: boolean = true): Promise<IPPersona> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/personas/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: isActive })
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to activate persona')
  }
  return response.json()
}

export async function fetchProducts(userId?: string): Promise<ProductVaultItem[]> {
  const url = userId
    ? `${API_BASE_URL}/api/dna/v2/products?user_id=${encodeURIComponent(userId)}`
    : `${API_BASE_URL}/api/dna/v2/products`
  const response = await apiFetch(url)
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch products')
  }
  return response.json()
}

export async function createProduct(data: Partial<ProductVaultItem>): Promise<ProductVaultItem> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to create product')
  }
  return response.json()
}

export async function updateProduct(
  id: string,
  data: Partial<ProductVaultItem>
): Promise<ProductVaultItem> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/products/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to update product')
  }
  return response.json()
}

export async function deleteProduct(id: string): Promise<{ success: boolean; message?: string }> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/products/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to delete product')
  }
  return response.json()
}

export async function uploadProductImage(file: File): Promise<{ success: boolean; url: string; filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/products/upload-image`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || error.message || 'Failed to upload product image')
  }
  return response.json()
}

export function resolveImageUrl(url?: string): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:') || url.startsWith('blob:')) {
    return url
  }
  const base = API_BASE_URL.replace(/\/$/, '')
  return `${base}${url.startsWith('/') ? '' : '/'}${url}`
}

export interface ExtractedProductResult {
  product: ProductVaultItem
  saved?: boolean
  message?: string
}

export async function extractProductFromText(
  text: string,
  autoSave?: boolean
): Promise<ExtractedProductResult> {
  const response = await apiFetch(`${API_BASE_URL}/api/dna/v2/products/extract-from-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      auto_save: autoSave ?? false,
      autoSave: autoSave ?? false,
    }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to extract product from text')
  }
  return response.json()
}
