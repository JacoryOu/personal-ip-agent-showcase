import { API_BASE_URL, apiFetch } from './client'
import type { ConnectionTestResult } from './client'
import { getImageHeaders, currentImageModel, customImageApiKey, customImageBaseUrl, currentImageResolution } from '../modelSettings'

export interface ImageGeneratePayload {
  prompt: string
  size?: string
  style?: string
  platform?: string
  aspect_ratio?: string
  model?: string
  api_key?: string
  base_url?: string
}

export interface ImageGenerateResult {
  image_url: string
  prompt: string
  revised_prompt?: string
  is_fallback?: boolean
  size?: string
  model?: string
}

export async function generateAiImage(
  payload: ImageGeneratePayload
): Promise<ImageGenerateResult> {
  const imageHeaders = getImageHeaders()
  const effectivePayload: ImageGeneratePayload = {
    ...payload,
    model: payload.model || currentImageModel.value || undefined,
    api_key: payload.api_key || (customImageApiKey.value.trim() ? customImageApiKey.value.trim() : undefined),
    base_url: payload.base_url || (customImageBaseUrl.value.trim() ? customImageBaseUrl.value.trim() : undefined),
    size: payload.size || currentImageResolution.value || undefined,
  }

  // apiFetch attaches the local MVP identity (X-API-Key) while leaving the
  // image model's own headers untouched.
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...imageHeaders,
  }

  const response = await apiFetch(`${API_BASE_URL}/api/images/generate`, {
    method: 'POST',
    headers,
    body: JSON.stringify(effectivePayload),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const msg = errorData.detail || errorData.message || `Image generation failed with status ${response.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return response.json()
}

export async function testImageConnection(params: {
  api_key?: string
  base_url?: string
  model?: string
}): Promise<ConnectionTestResult> {
  const startTime = Date.now()
  try {
    const res = await generateAiImage({
      prompt: "Agnes Gateway Connection Verification",
      platform: "xiaohongshu",
      aspect_ratio: "3:4",
      api_key: params.api_key,
      base_url: params.base_url,
      model: params.model,
    })
    const latency = Date.now() - startTime
    if (res.is_fallback) {
      return {
        success: false,
        latency_ms: latency,
        model: res.model || params.model || 'agnes-image-2.5-flash',
        message: '未配置真实 API Key 或云端服务离线，系统已平滑切换至高质量原生 SVG 意境图兜底。',
      }
    }
    return {
      success: true,
      latency_ms: latency,
      model: res.model || params.model || 'agnes-image-2.5-flash',
      message: `生图引擎联通成功！当前画质尺寸: ${res.size || '2K (3:4)'}`,
    }
  } catch (err: any) {
    const latency = Date.now() - startTime
    return {
      success: false,
      latency_ms: latency,
      model: params.model || 'agnes-image-2.5-flash',
      message: err.message || 'Image engine connection failed',
    }
  }
}

export async function fetchImageAsDataUri(imageUrl: string): Promise<string> {
  if (!imageUrl) return ''
  if (imageUrl.startsWith('data:')) return imageUrl

  try {
    const res = await fetch(imageUrl, { mode: 'cors' })
    if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
    const blob = await res.blob()
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(blob)
    })
  } catch (err) {
    // If CORS or network fetch fails, return original or fallback
    return imageUrl
  }
}
