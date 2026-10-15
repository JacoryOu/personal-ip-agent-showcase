import { ref, computed } from 'vue'

export interface ModelPreset {
  id: string
  name: string
  icon: string
  badgeZh: string
  badgeEn: string
  descriptionZh: string
  descriptionEn: string
  defaultProviderId: string
  defaultModelName: string
}

export interface ProviderPreset {
  id: string
  nameZh: string
  nameEn: string
  baseUrl: string
  icon: string
  recommendedModels: string[]
  requiresApiKey: boolean
  apiKeyPlaceholder: string
}

export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: 'system',
    nameZh: '系统内置 (.env 默认)',
    nameEn: 'System Default (.env)',
    baseUrl: '',
    icon: '⚡',
    recommendedModels: [],
    requiresApiKey: false,
    apiKeyPlaceholder: '使用后端已配置密钥 (无需输入)',
  },
  {
    id: 'aliyun',
    nameZh: '阿里云百炼 (DashScope)',
    nameEn: 'Aliyun DashScope',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    icon: '☁️',
    recommendedModels: ['qwen-max', 'qwen-plus', 'deepseek-v3', 'deepseek-r1'],
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-...',
  },
  {
    id: 'deepseek',
    nameZh: 'DeepSeek 官方',
    nameEn: 'DeepSeek Official',
    baseUrl: 'https://api.deepseek.com/v1',
    icon: '⚡',
    recommendedModels: ['deepseek-chat', 'deepseek-reasoner'],
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-...',
  },
  {
    id: 'siliconflow',
    nameZh: '硅基流动 (SiliconFlow)',
    nameEn: 'SiliconFlow',
    baseUrl: 'https://api.siliconflow.cn/v1',
    icon: '🌊',
    recommendedModels: ['deepseek-ai/DeepSeek-V3', 'deepseek-ai/DeepSeek-R1', 'Qwen/Qwen2.5-72B-Instruct'],
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-...',
  },
  {
    id: 'ollama',
    nameZh: '本地 Ollama',
    nameEn: 'Local Ollama',
    baseUrl: 'http://localhost:11434/v1',
    icon: '🦙',
    recommendedModels: ['deepseek-r1:8b', 'qwen2.5:7b', 'llama3.3'],
    requiresApiKey: false,
    apiKeyPlaceholder: '无需密钥 (No Key Needed)',
  },
  {
    id: 'agnes',
    nameZh: 'Agnes AI 生图/推理引擎',
    nameEn: 'Agnes AI Platform',
    baseUrl: 'https://apihub.agnes-ai.com/v1',
    icon: '✨',
    recommendedModels: ['agnes-image-2.5-flash'],
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-... (Agnes API Key)',
  },
  {
    id: 'custom',
    nameZh: '自定义代理 / 其他',
    nameEn: 'Custom Proxy / Other',
    baseUrl: '',
    icon: '🌐',
    recommendedModels: [],
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-...',
  },
]

export const MODEL_PRESETS: ModelPreset[] = [
  {
    id: 'system',
    name: '系统内置默认',
    icon: '⚡',
    badgeZh: '即开即用·无需配置',
    badgeEn: 'Ready · No Key Needed',
    descriptionZh: '使用后端 .env 预配置的服务商与模型，免配密钥直接创作',
    descriptionEn: 'Uses backend .env preconfigured provider & model',
    defaultProviderId: 'system',
    defaultModelName: '',
  },
  {
    id: 'deepseek-v3',
    name: 'DeepSeek-V3',
    icon: '⚡',
    badgeZh: '推荐·均衡高速',
    badgeEn: 'Recommended · Fast & Balanced',
    descriptionZh: '全能旗舰模型，行文流畅自然，响应极速',
    descriptionEn: 'Flagship model, smooth natural prose and ultrafast response',
    defaultProviderId: 'deepseek',
    defaultModelName: 'deepseek-chat',
  },
  {
    id: 'deepseek-r1',
    name: 'DeepSeek-R1',
    icon: '🧠',
    badgeZh: '深度思考·逻辑爆发',
    badgeEn: 'Deep Thinking · Strong Logic',
    descriptionZh: '具备强大推理链，适合深度论点提炼与逆向思辨',
    descriptionEn: 'Exceptional reasoning chains for contrarian thinking & structural depth',
    defaultProviderId: 'deepseek',
    defaultModelName: 'deepseek-reasoner',
  },
  {
    id: 'qwen-max',
    name: '通义千问 Qwen-Max',
    icon: '🛡️',
    badgeZh: '扎实厚重·中文语境',
    badgeEn: 'Solid & Authoritative',
    descriptionZh: '阿里云顶尖中文大模型，文风严谨典雅，商业认知深厚',
    descriptionEn: 'Alibaba tier-1 Chinese model, authoritative & rigorous',
    defaultProviderId: 'aliyun',
    defaultModelName: 'qwen-max',
  },
  {
    id: 'claude-3-7-sonnet',
    name: 'Claude 3.7 Sonnet',
    icon: '🎭',
    badgeZh: '顶级文笔·细腻灵动',
    badgeEn: 'Supreme Prose · Nuanced',
    descriptionZh: 'Anthropic 前沿模型，兼具超高文学素养与结构严谨性',
    descriptionEn: 'Anthropic frontier model, exquisite literary taste & nuanced tone',
    defaultProviderId: 'custom',
    defaultModelName: 'claude-3-7-sonnet-20250219',
  },
  {
    id: 'gpt-4o',
    name: 'OpenAI GPT-4o',
    icon: '🌐',
    badgeZh: '全能通用·标准标杆',
    badgeEn: 'Omnipotent · Industry Benchmark',
    descriptionZh: '通用多模态标杆模型，执行力强，逻辑稳定',
    descriptionEn: 'Industry benchmark, highly stable instruction-following',
    defaultProviderId: 'custom',
    defaultModelName: 'gpt-4o',
  },
  {
    id: 'custom',
    name: '自定义模型',
    icon: '⚙️',
    badgeZh: '自由配置',
    badgeEn: 'Custom Model',
    descriptionZh: '自由指定模型名称、Base URL 与 API Key',
    descriptionEn: 'Freely customize model name, endpoint URL and API Key',
    defaultProviderId: 'custom',
    defaultModelName: '',
  },
]

// AI Image Engine Preset Definitions
export interface ImageProviderPreset {
  id: string
  nameZh: string
  nameEn: string
  model: string
  baseUrl: string
  icon: string
  badgeZh: string
  badgeEn: string
  descriptionZh: string
  descriptionEn: string
  requiresApiKey: boolean
  apiKeyPlaceholder: string
  supportedResolutions: string[]
}

export const IMAGE_PROVIDER_PRESETS: ImageProviderPreset[] = [
  {
    id: 'agnes',
    nameZh: 'Agnes Image 2.5 Flash',
    nameEn: 'Agnes Image 2.5 Flash',
    model: 'agnes-image-2.5-flash',
    baseUrl: 'https://apihub.agnes-ai.com/v1',
    icon: '✨',
    badgeZh: '官方旗舰·免费超清',
    badgeEn: 'Flagship · Free UltraHD',
    descriptionZh: '支持 1K-4K 高清分辨率与原生 3:4/16:9 比例，专为小红书与公众号打造',
    descriptionEn: 'Supports 1K-4K resolution & 3:4 / 16:9 ratios, optimized for social media',
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-... (Agnes API Key)',
    supportedResolutions: ['1K', '2K', '3K', '4K'],
  },
  {
    id: 'dalle3',
    nameZh: 'OpenAI DALL-E 3',
    nameEn: 'OpenAI DALL-E 3',
    model: 'dall-e-3',
    baseUrl: 'https://api.openai.com/v1',
    icon: '🌐',
    badgeZh: '行业通用标杆',
    badgeEn: 'Industry Benchmark',
    descriptionZh: 'OpenAI 经典生图大模型，指令遵循能力优异',
    descriptionEn: 'OpenAI benchmark multimodal image model with solid prompt following',
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-... (OpenAI Key)',
    supportedResolutions: ['1024x1792', '1792x1024', '1024x1024'],
  },
  {
    id: 'wanx',
    nameZh: '阿里通义万相 (DashScope)',
    nameEn: 'Aliyun Wanx',
    model: 'wanx-v1',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    icon: '☁️',
    badgeZh: '中文东方美学',
    badgeEn: 'Oriental Aesthetics',
    descriptionZh: '阿里云官方生图模型，深谙中文文化与国风质感',
    descriptionEn: 'Alibaba image generation model specialized in Chinese visual styles',
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-... (DashScope Key)',
    supportedResolutions: ['1024*1024', '768*1024', '1024*768'],
  },
  {
    id: 'custom',
    nameZh: '自定义生图服务',
    nameEn: 'Custom Image Provider',
    model: '',
    baseUrl: '',
    icon: '⚙️',
    badgeZh: '自由配置',
    badgeEn: 'Custom Service',
    descriptionZh: '自由指定兼容的 Base URL 与生图模型名称',
    descriptionEn: 'Freely specify custom compatible image endpoint and model',
    requiresApiKey: true,
    apiKeyPlaceholder: 'sk-...',
    supportedResolutions: ['2K', '1K'],
  },
]

// LocalStorage Keys for Text LLM
const STORAGE_KEY_MODEL = 'ip_engine_current_model'
const STORAGE_KEY_PROVIDER = 'ip_engine_provider_id'
const STORAGE_KEY_API_KEY = 'ip_engine_custom_api_key'
const STORAGE_KEY_BASE_URL = 'ip_engine_custom_base_url'
const STORAGE_KEY_CUSTOM_MODEL_NAME = 'ip_engine_custom_model_name'

// LocalStorage Keys for Image Engine
const STORAGE_KEY_IMAGE_PROVIDER = 'ip_engine_image_provider_id'
const STORAGE_KEY_IMAGE_MODEL = 'ip_engine_image_model'
const STORAGE_KEY_IMAGE_API_KEY = 'ip_engine_image_api_key'
const STORAGE_KEY_IMAGE_BASE_URL = 'ip_engine_image_base_url'
const STORAGE_KEY_IMAGE_RESOLUTION = 'ip_engine_image_resolution'

// Reactive States for Text LLM
export const currentModel = ref<string>(localStorage.getItem(STORAGE_KEY_MODEL) || 'system')
export const currentProviderId = ref<string>(localStorage.getItem(STORAGE_KEY_PROVIDER) || 'system')
export const customApiKey = ref<string>(localStorage.getItem(STORAGE_KEY_API_KEY) || '')
export const customBaseUrl = ref<string>(localStorage.getItem(STORAGE_KEY_BASE_URL) || '')
export const customModelName = ref<string>(localStorage.getItem(STORAGE_KEY_CUSTOM_MODEL_NAME) || '')

// Server-side backend configuration states (from GET /api/settings/current)
export const serverModelName = ref<string>('')
export const serverBaseUrl = ref<string>('')
export const serverHasKey = ref<boolean>(false)
export const serverMaskedKey = ref<string>('')

// Reactive States for Image Engine
export const currentImageProviderId = ref<string>(localStorage.getItem(STORAGE_KEY_IMAGE_PROVIDER) || 'agnes')
export const currentImageModel = ref<string>(localStorage.getItem(STORAGE_KEY_IMAGE_MODEL) || 'agnes-image-2.5-flash')
export const customImageApiKey = ref<string>(localStorage.getItem(STORAGE_KEY_IMAGE_API_KEY) || '')
export const customImageBaseUrl = ref<string>(localStorage.getItem(STORAGE_KEY_IMAGE_BASE_URL) || 'https://apihub.agnes-ai.com/v1')
export const currentImageResolution = ref<string>(localStorage.getItem(STORAGE_KEY_IMAGE_RESOLUTION) || '2K')

export const activeModelPreset = computed(() => {
  return MODEL_PRESETS.find((m) => m.id === currentModel.value) || MODEL_PRESETS[0]
})

export function resolveActualModelName(modelId: string, providerId: string): string {
  if (modelId === 'system') return ''
  if (modelId === 'custom') return customModelName.value.trim() || 'gpt-4o'

  if (providerId === 'deepseek') {
    if (modelId === 'deepseek-v3') return 'deepseek-chat'
    if (modelId === 'deepseek-r1') return 'deepseek-reasoner'
  } else if (providerId === 'aliyun') {
    if (modelId === 'deepseek-v3') return 'deepseek-v3'
    if (modelId === 'deepseek-r1') return 'deepseek-r1'
    if (modelId === 'qwen-max') return 'qwen-max'
  } else if (providerId === 'siliconflow') {
    if (modelId === 'deepseek-v3') return 'deepseek-ai/DeepSeek-V3'
    if (modelId === 'deepseek-r1') return 'deepseek-ai/DeepSeek-R1'
  }
  const preset = MODEL_PRESETS.find((m) => m.id === modelId)
  return preset?.defaultModelName || modelId
}

export const effectiveModelName = computed(() => {
  return resolveActualModelName(currentModel.value, currentProviderId.value)
})

export const activeImageProviderPreset = computed(() => {
  return IMAGE_PROVIDER_PRESETS.find((p) => p.id === currentImageProviderId.value) || IMAGE_PROVIDER_PRESETS[0]
})

export function setCurrentModel(modelId: string) {
  currentModel.value = modelId
  localStorage.setItem(STORAGE_KEY_MODEL, modelId)
}

export function saveModelSettings(settings: {
  model: string
  providerId: string
  apiKey: string
  baseUrl: string
  customModelName?: string
}) {
  currentModel.value = settings.model
  currentProviderId.value = settings.providerId
  customApiKey.value = settings.apiKey.trim()
  customBaseUrl.value = settings.baseUrl.trim()
  if (settings.customModelName !== undefined) {
    customModelName.value = settings.customModelName.trim()
  }

  localStorage.setItem(STORAGE_KEY_MODEL, currentModel.value)
  localStorage.setItem(STORAGE_KEY_PROVIDER, currentProviderId.value)
  localStorage.setItem(STORAGE_KEY_API_KEY, customApiKey.value)
  localStorage.setItem(STORAGE_KEY_BASE_URL, customBaseUrl.value)
  localStorage.setItem(STORAGE_KEY_CUSTOM_MODEL_NAME, customModelName.value)
}

export function resetModelSettings() {
  currentModel.value = 'system'
  currentProviderId.value = 'system'
  customApiKey.value = ''
  customBaseUrl.value = ''
  customModelName.value = ''

  localStorage.removeItem(STORAGE_KEY_MODEL)
  localStorage.removeItem(STORAGE_KEY_PROVIDER)
  localStorage.removeItem(STORAGE_KEY_API_KEY)
  localStorage.removeItem(STORAGE_KEY_BASE_URL)
  localStorage.removeItem(STORAGE_KEY_CUSTOM_MODEL_NAME)
}

export function saveImageSettings(settings: {
  providerId: string
  model: string
  apiKey: string
  baseUrl: string
  resolution?: string
}) {
  currentImageProviderId.value = settings.providerId
  currentImageModel.value = settings.model.trim() || 'agnes-image-2.5-flash'
  customImageApiKey.value = settings.apiKey.trim()
  customImageBaseUrl.value = settings.baseUrl.trim() || 'https://apihub.agnes-ai.com/v1'
  if (settings.resolution) {
    currentImageResolution.value = settings.resolution
  }

  localStorage.setItem(STORAGE_KEY_IMAGE_PROVIDER, currentImageProviderId.value)
  localStorage.setItem(STORAGE_KEY_IMAGE_MODEL, currentImageModel.value)
  localStorage.setItem(STORAGE_KEY_IMAGE_API_KEY, customImageApiKey.value)
  localStorage.setItem(STORAGE_KEY_IMAGE_BASE_URL, customImageBaseUrl.value)
  localStorage.setItem(STORAGE_KEY_IMAGE_RESOLUTION, currentImageResolution.value)
}

export function resetImageSettings() {
  currentImageProviderId.value = 'agnes'
  currentImageModel.value = 'agnes-image-2.5-flash'
  customImageApiKey.value = ''
  customImageBaseUrl.value = 'https://apihub.agnes-ai.com/v1'
  currentImageResolution.value = '2K'

  localStorage.removeItem(STORAGE_KEY_IMAGE_PROVIDER)
  localStorage.removeItem(STORAGE_KEY_IMAGE_MODEL)
  localStorage.removeItem(STORAGE_KEY_IMAGE_API_KEY)
  localStorage.removeItem(STORAGE_KEY_IMAGE_BASE_URL)
  localStorage.removeItem(STORAGE_KEY_IMAGE_RESOLUTION)
}

export function getModelHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  // System mode uses backend's .env natively without override
  if (currentProviderId.value === 'system') {
    return headers
  }
  const model = effectiveModelName.value
  if (model) {
    headers['X-Model-Name'] = model
  }
  if (customApiKey.value.trim()) {
    headers['X-Model-Api-Key'] = customApiKey.value.trim()
  }
  if (customBaseUrl.value.trim()) {
    headers['X-Base-Url'] = customBaseUrl.value.trim()
  }
  return headers
}

export function getImageHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const model = currentImageModel.value.trim()
  if (model) {
    headers['X-Image-Model'] = model
  }
  if (customImageApiKey.value.trim()) {
    headers['X-Image-Api-Key'] = customImageApiKey.value.trim()
  }
  if (customImageBaseUrl.value.trim()) {
    headers['X-Image-Base-Url'] = customImageBaseUrl.value.trim()
  }
  return headers
}
