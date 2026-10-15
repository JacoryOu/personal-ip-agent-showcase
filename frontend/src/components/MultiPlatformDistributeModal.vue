<script setup lang="ts">
import JSZip from 'jszip'
import { ref, watch, computed } from 'vue'
import {
  distributeContent,
  distributeDraftById,
  generateAiImage,
  fetchImageAsDataUri,
  type DistributionResult,
  type XhsCard,
  type WechatCoverImage,
  type WechatQuoteCard,
} from '../services/api'
import {
  renderXhsCardToCanvas,
  renderXhsCompositeCoverToCanvas,
  renderWechatCoverToCanvas,
  renderWechatQuoteToCanvas,
  downloadCanvasAsPng,
  downloadImageFromUrl,
  type VisualTheme,
} from '../utils/cardCanvasExporter'
import {
  DOOCS_THEMES,
  type DoocsThemeKey,
  type SectionIllustration,
  renderWechatHtmlWithDoocs,
  extractSectionsFromMarkdown,
  copyDoocsHtmlToClipboard,
  copySingleImageToClipboard,
} from '../utils/doocsRenderer'
import { useI18n } from '../i18n'
import { currentImageModel, currentImageResolution } from '../services/modelSettings'

interface Props {
  show: boolean
  content?: string
  title?: string
  draftId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'close'): void
}>()

const { t, locale } = useI18n()

const activeImageEngineLabel = computed(() => {
  const model = currentImageModel.value || 'agnes-image-2.5-flash'
  const res = currentImageResolution.value || '2K'
  if (model.toLowerCase().includes('agnes')) {
    return `Agnes Image 2.5 Flash · ${res}超清`
  }
  return `${model} · ${res}`
})

type PlatformKey = 'xiaohongshu' | 'wechat' | 'twitter' | 'video'
const activeTab = ref<PlatformKey>('xiaohongshu')
const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<DistributionResult | null>(null)
const copiedPlatform = ref<string | null>(null)

// Sub-mode tabs
const xhsMode = ref<'cards' | 'copy'>('cards')
const wechatMode = ref<'layout' | 'visual' | 'text'>('layout')
const wechatDoocsTheme = ref<DoocsThemeKey>('emerald')
const sectionIllustrations = ref<SectionIllustration[]>([])
const isGeneratingAllIllustrations = ref(false)
const illustrationProgress = ref({ current: 0, total: 0 })
const generatingSectionId = ref<string | null>(null)
const copiedSectionImgId = ref<string | null>(null)
const copiedDoocsRich = ref(false)
const isZippingWechat = ref(false)
const includeHeaderInBody = ref(false)
const copiedTitle = ref(false)
const copiedAuthor = ref(false)
const copiedBody = ref(false)
const wechatAssistantToast = ref<string | null>(null)

const articleTitle = computed(() => {
  return currentPlatformData.value?.title || props.title || result.value?.title || ''
})

const authorName = computed(() => {
  return currentPlatformData.value?.cover_image?.author || '个人认知 IP 引擎'
})

async function handleCopyTitle() {
  if (!articleTitle.value) return
  try {
    await navigator.clipboard.writeText(articleTitle.value)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = articleTitle.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copiedTitle.value = true
  wechatAssistantToast.value = t.value.distribute.titleCopiedToast
  setTimeout(() => {
    copiedTitle.value = false
    if (wechatAssistantToast.value === t.value.distribute.titleCopiedToast) {
      wechatAssistantToast.value = null
    }
  }, 3500)
}

async function handleCopyAuthor() {
  if (!authorName.value) return
  try {
    await navigator.clipboard.writeText(authorName.value)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = authorName.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copiedAuthor.value = true
  wechatAssistantToast.value = t.value.distribute.authorCopiedToast
  setTimeout(() => {
    copiedAuthor.value = false
    if (wechatAssistantToast.value === t.value.distribute.authorCopiedToast) {
      wechatAssistantToast.value = null
    }
  }, 3500)
}
const zipWechatProgress = ref('')

// Card theme & active index
const selectedTheme = ref<VisualTheme>('dark_gold')
const activeXhsCardIdx = ref(0)
const xhsCardViewMode = ref<'carousel' | 'grid'>('carousel')
const isDownloadingAll = ref(false)

// AI Image Generation state for Xiaohongshu
const aiImagePrompt = ref('')
const aiImageUrl = ref<string | null>(null)
const isGeneratingAiImage = ref(false)
const aiImageError = ref<string | null>(null)
const aiImageSuccess = ref(false)
const aiImagePreviewMode = ref<'composite' | 'pure'>('composite')
const isFallbackAiImage = ref(false)

const tabs = computed(() => [
  { key: 'xiaohongshu' as PlatformKey, label: t.value.distribute.tabXiaohongshu },
  { key: 'wechat' as PlatformKey, label: t.value.distribute.tabWechat },
  { key: 'twitter' as PlatformKey, label: t.value.distribute.tabTwitter },
  { key: 'video' as PlatformKey, label: t.value.distribute.tabVideo },
])

const currentPlatformData = computed(() => {
  if (!result.value?.platforms) return null
  return result.value.platforms[activeTab.value] || null
})

const xhsCards = computed<XhsCard[]>(() => {
  return currentPlatformData.value?.cards || []
})

// ─── Unified Canvas Preview ────────────────────────────────────────────────
// Instead of maintaining a parallel HTML layout, we render every card through
// the SAME Canvas functions used for download, then display them as <img> tags.
// This guarantees preview == download, pixel-perfect.
const xhsPreviewImages = ref<string[]>([])
const isGeneratingPreviews = ref(false)

async function generateXhsPreviews() {
  const cards = xhsCards.value
  if (!cards.length) { xhsPreviewImages.value = []; return }

  isGeneratingPreviews.value = true
  const urls: string[] = []

  // Proxy the AI image once for the whole batch (same as downloadAllXhsCardsAsZip)
  let proxiedAiUrl = aiImageUrl.value
  if (proxiedAiUrl && !proxiedAiUrl.startsWith('data:')) {
    try { proxiedAiUrl = await fetchImageAsDataUri(proxiedAiUrl) } catch { proxiedAiUrl = null }
  }

  for (let i = 0; i < cards.length; i++) {
    const card = cards[i]
    try {
      let canvas: HTMLCanvasElement
      if (card.card_type === 'cover') {
        canvas = await renderXhsCompositeCoverToCanvas(
          card, proxiedAiUrl || undefined, selectedTheme.value, '个人认知 IP 引擎', i + 1, cards.length
        )
      } else {
        canvas = renderXhsCardToCanvas(card, selectedTheme.value, '个人认知 IP 引擎', i + 1, cards.length)
      }
      urls.push(canvas.toDataURL('image/png'))
    } catch (e) {
      // On error push empty so indices stay aligned
      urls.push('')
    }
  }

  xhsPreviewImages.value = urls
  isGeneratingPreviews.value = false
}

// Regenerate previews whenever cards, theme, or AI image change
watch(
  [xhsCards, selectedTheme, aiImageUrl],
  () => { generateXhsPreviews() },
  { deep: false }
)

const wechatCover = computed<WechatCoverImage | null>(() => {
  return currentPlatformData.value?.cover_image || null
})

const wechatQuote = computed<WechatQuoteCard | null>(() => {
  return currentPlatformData.value?.quote_card || null
})

const wechatPrompts = computed(() => {
  return currentPlatformData.value?.image_prompts || []
})

// ─── Carousel Single-Card Canvas Preview ─────────────────────────────────────
// Same Canvas renderer as download — triggered when active card or theme changes.
const xhsCarouselPreviewImage = ref<string>('')
const isRenderingCarouselPreview = ref(false)

async function generateCarouselPreview() {
  const cards = xhsCards.value
  const idx = activeXhsCardIdx.value
  const card = cards[idx]
  if (!card) { xhsCarouselPreviewImage.value = ''; return }

  isRenderingCarouselPreview.value = true
  try {
    let proxiedAiUrl = aiImageUrl.value
    if (proxiedAiUrl && !proxiedAiUrl.startsWith('data:')) {
      try { proxiedAiUrl = await fetchImageAsDataUri(proxiedAiUrl) } catch { proxiedAiUrl = null }
    }
    let canvas: HTMLCanvasElement
    if (card.card_type === 'cover') {
      canvas = await renderXhsCompositeCoverToCanvas(
        card, proxiedAiUrl || undefined, selectedTheme.value, '个人认知 IP 引擎', idx + 1, cards.length
      )
    } else {
      canvas = renderXhsCardToCanvas(card, selectedTheme.value, '个人认知 IP 引擎', idx + 1, cards.length)
    }
    xhsCarouselPreviewImage.value = canvas.toDataURL('image/png')
  } catch {
    xhsCarouselPreviewImage.value = ''
  } finally {
    isRenderingCarouselPreview.value = false
  }
}

watch([activeXhsCardIdx, selectedTheme, aiImageUrl, xhsCards], () => {
  generateCarouselPreview()
}, { deep: false })

// ─── WeChat Visual Canvas Previews ────────────────────────────────────────────
// Same Canvas renderers as download buttons.
const wechatCoverPreviewImage = ref<string>('')
const wechatQuotePreviewImage = ref<string>('')

async function generateWechatPreviews() {
  if (wechatCover.value) {
    try {
      const c = renderWechatCoverToCanvas(wechatCover.value, selectedTheme.value)
      wechatCoverPreviewImage.value = c.toDataURL('image/png')
    } catch { wechatCoverPreviewImage.value = '' }
  } else {
    wechatCoverPreviewImage.value = ''
  }
  if (wechatQuote.value) {
    try {
      const c = renderWechatQuoteToCanvas(wechatQuote.value, selectedTheme.value)
      wechatQuotePreviewImage.value = c.toDataURL('image/png')
    } catch { wechatQuotePreviewImage.value = '' }
  } else {
    wechatQuotePreviewImage.value = ''
  }
}

watch([wechatCover, wechatQuote, selectedTheme], () => {
  generateWechatPreviews()
}, { deep: false })



// Auto-sync suggested prompt from cover card
watch(
  () => currentPlatformData.value,
  (data) => {
    if (data?.cover) {
      if (!aiImagePrompt.value || aiImagePrompt.value.trim() === '') {
        aiImagePrompt.value = data.cover.suggested_prompt || data.cover.image_prompt || `${data.cover.title || result.value?.title || ''} 极简商业概念摄影，留白构图`
      }
    } else if (data?.cards?.[0]) {
      const c = data.cards[0]
      if (!aiImagePrompt.value || aiImagePrompt.value.trim() === '') {
        aiImagePrompt.value = c.suggested_prompt || c.image_prompt || `${c.title || result.value?.title || ''} 极简商业概念摄影，留白构图`
      }
    }
  },
  { immediate: true }
)

async function fetchDistribution() {
  if (!props.show) return
  if (!props.content && !props.draftId) {
    error.value = t.value.distribute.empty
    return
  }

  loading.value = true
  error.value = null

  try {
    if (props.draftId) {
      result.value = await distributeDraftById(props.draftId)
    } else if (props.content) {
      result.value = await distributeContent({
        content: props.content,
        title: props.title,
      })
    }
  } catch (err: any) {
    error.value = err.message || 'Distribution formatting failed.'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (val) => {
    if (val) {
      if (!result.value || props.content) {
        fetchDistribution()
      }
    }
  },
  { immediate: true }
)

function closeModal() {
  emit('update:show', false)
  emit('close')
}

async function copyText(text: string, platformKey: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedPlatform.value = platformKey
    setTimeout(() => {
      if (copiedPlatform.value === platformKey) {
        copiedPlatform.value = null
      }
    }, 2500)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copiedPlatform.value = platformKey
    setTimeout(() => {
      if (copiedPlatform.value === platformKey) {
        copiedPlatform.value = null
      }
    }, 2500)
  }
}

// AI Image Generation handler
async function handleGenerateAiImage() {
  const prompt = aiImagePrompt.value.trim()
  if (!prompt) return

  isGeneratingAiImage.value = true
  aiImageError.value = null
  aiImageSuccess.value = false

  try {
    const res = await generateAiImage({
      prompt,
      platform: 'xiaohongshu',
      aspect_ratio: '3:4',
      style: selectedTheme.value,
    })
    aiImageUrl.value = res.image_url
    isFallbackAiImage.value = !!res.is_fallback
    aiImageSuccess.value = true
    setTimeout(() => {
      aiImageSuccess.value = false
    }, 4000)
  } catch (err: any) {
    aiImageError.value = err.message || 'AI 生图服务暂时不可用'
  } finally {
    isGeneratingAiImage.value = false
  }
}

// Download handlers
async function downloadCompositeCoverImage() {
  const coverCard = xhsCards.value[0] || currentPlatformData.value?.cover
  if (!coverCard) return
  let proxiedAiImageUrl = aiImageUrl.value
  if (proxiedAiImageUrl && !proxiedAiImageUrl.startsWith('data:')) {
    try {
      proxiedAiImageUrl = await fetchImageAsDataUri(proxiedAiImageUrl)
    } catch (e) {
      console.warn('Failed to fetch data uri', e)
    }
  }
  const canvas = await renderXhsCompositeCoverToCanvas(
    coverCard,
    proxiedAiImageUrl || undefined,
    selectedTheme.value,
    '个人认知 IP 引擎',
    1,
    xhsCards.value.length || 1
  )
  const filename = `小红书_AI大字报首图_${(coverCard.title || '封面').slice(0, 15)}`
  downloadCanvasAsPng(canvas, filename)
}

async function downloadPureAiBackground() {
  if (!aiImageUrl.value) return
  const coverCard = xhsCards.value[0] || currentPlatformData.value?.cover
  const filename = `小红书_纯净AI背景_${(coverCard?.title || '背景').slice(0, 15)}`
  try {
    const dataUri = await fetchImageAsDataUri(aiImageUrl.value)
    const a = document.createElement('a')
    a.href = dataUri
    a.download = filename
    a.click()
    a.remove()
  } catch (e) {
    console.warn('Failed to download pure AI background', e)
  }
}

async function downloadCurrentXhsCard() {
  const cards = xhsCards.value
  if (!cards.length) return
  const idx = activeXhsCardIdx.value
  const card = cards[idx]
  let canvas: HTMLCanvasElement
  if (idx === 0 && (aiImageUrl.value || card.card_type === 'cover')) {
    let proxiedAiImageUrl = aiImageUrl.value;
    if (proxiedAiImageUrl) { try { proxiedAiImageUrl = await fetchImageAsDataUri(proxiedAiImageUrl); } catch (e) {} }
    canvas = await renderXhsCompositeCoverToCanvas(
      card,
      proxiedAiImageUrl || undefined,
      selectedTheme.value,
      '个人认知 IP 引擎',
      idx + 1,
      cards.length
    )
  } else {
    canvas = renderXhsCardToCanvas(
      card,
      selectedTheme.value,
      '个人认知 IP 引擎',
      idx + 1,
      cards.length
    )
  }
  const filename = `小红书卡片_${idx + 1}_${(card.title || '卡片').slice(0, 15)}`
  downloadCanvasAsPng(canvas, filename)
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('Canvas conversion to blob failed'))
    }, 'image/png')
  })
}

// Module 5: JSZip One-Click Batch Download for Xiaohongshu Cards
const isZippingAll = ref(false)
const zipProgress = ref('')

async function downloadAllXhsCardsAsZip() {
  const cards = xhsCards.value
  if (!cards.length || isZippingAll.value) return
  isZippingAll.value = true
  zipProgress.value = '正在启动高画质渲染与打包引擎...'

  try {
    const zip = new JSZip()
    const folder = zip.folder(`小红书全套卡片_${(result.value?.title || '作品').slice(0, 15)}`)

    let proxiedAiImageUrl = aiImageUrl.value;
    if (proxiedAiImageUrl) { try { proxiedAiImageUrl = await fetchImageAsDataUri(proxiedAiImageUrl); } catch(e) {} }
    for (let i = 0; i < cards.length; i++) {
      const card = cards[i]
      zipProgress.value = `正在渲染第 ${i + 1}/${cards.length} 张 1080×1440 超清卡片...`
      
      if (i === 0) {
        if (aiImageUrl.value) {
          // 1. AI Composite Cover with Poster Typography
          const compCanvas = await renderXhsCompositeCoverToCanvas(
            card,
            proxiedAiImageUrl || undefined,
            selectedTheme.value,
            '个人认知 IP 引擎',
            1,
            cards.length
          )
          const compBlob = await canvasToBlob(compCanvas)
          folder?.file(`01_AI大字报合成首图_${(card.title || '封面').slice(0, 10)}.png`, compBlob)

          // 2. Pure AI Photo Background without text
          try {
            const pureBlob = await fetch(proxiedAiImageUrl!).then(r => r.blob())
            folder?.file('00_纯净AI意境原图_无字版.png', pureBlob)
          } catch (e) {
            console.warn('Failed to include raw AI image in zip', e)
          }

          // 3. Alternative Standard Theme Cover
          const themeCanvas = renderXhsCardToCanvas(
            card,
            selectedTheme.value,
            '个人认知 IP 引擎',
            1,
            cards.length
          )
          const themeBlob = await canvasToBlob(themeCanvas)
          folder?.file(`01_纯色排版备选封面_${(card.title || '封面').slice(0, 10)}.png`, themeBlob)
        } else {
          // Standard Theme Cover matching the current selected visual style exactly
          const themeCanvas = renderXhsCardToCanvas(
            card,
            selectedTheme.value,
            '个人认知 IP 引擎',
            1,
            cards.length
          )
          const themeBlob = await canvasToBlob(themeCanvas)
          folder?.file(`01_主题精修封面_${(card.title || '封面').slice(0, 10)}.png`, themeBlob)
        }
      } else {
        // Inner point cards and summary card matching the current preview
        const canvas = renderXhsCardToCanvas(
          card,
          selectedTheme.value,
          '个人认知 IP 引擎',
          i + 1,
          cards.length
        )
        const blob = await canvasToBlob(canvas)
        const typeLabel = card.card_type === 'summary'
          ? `${String(i + 1).padStart(2, '0')}_尾页复盘清单`
          : `${String(i + 1).padStart(2, '0')}_核心要点`
        folder?.file(`${typeLabel}_${(card.title || '卡片').slice(0, 10)}.png`, blob)
      }
    }

    // Add note copywriting & hashtags
    const noteText = `${currentPlatformData.value?.title || result.value?.title || ''}

${currentPlatformData.value?.content || ''}

话题标签：${(currentPlatformData.value?.tags || []).join(' ')}`
    folder?.file('小红书笔记文案与话题标签.txt', noteText)

    zipProgress.value = '正在极速压缩打包为 ZIP...'
    const zipBlob = await zip.generateAsync({ type: 'blob' })
    const zipFilename = `小红书全套卡片_${(result.value?.title || '作品').slice(0, 15)}.zip`
    const a = document.createElement('a')
    a.href = URL.createObjectURL(zipBlob)
    a.download = zipFilename
    a.click()
    a.remove()
  } catch (err: any) {
    alert(err.message || '打包 ZIP 失败')
  } finally {
    isZippingAll.value = false
    zipProgress.value = ''
  }
}

async function downloadAllXhsCards() {
  await downloadAllXhsCardsAsZip()
}

function downloadWechatCoverImage() {
  if (!wechatCover.value) return
  const canvas = renderWechatCoverToCanvas(wechatCover.value, selectedTheme.value)
  const filename = `公众号官方封面_900x383_${wechatCover.value.title.slice(0, 15)}`
  downloadCanvasAsPng(canvas, filename)
}

function downloadWechatQuoteImage() {
  if (!wechatQuote.value) return
  const canvas = renderWechatQuoteToCanvas(wechatQuote.value, selectedTheme.value)
  const filename = `公众号金句插图_16x9_${wechatQuote.value.source.slice(0, 15)}`
  downloadCanvasAsPng(canvas, filename)
}

// WeChat doocs/md Layout and Illustration Engine
watch(
  () => [currentPlatformData.value, activeTab.value, props.content],
  () => {
    if (activeTab.value === 'wechat') {
      const data = currentPlatformData.value
      if (data?.section_illustrations && data.section_illustrations.length > 0) {
        const existingMap = new Map(sectionIllustrations.value.map(s => [s.section_index, s.image_url]))
        sectionIllustrations.value = data.section_illustrations.map((item, idx) => ({
          ...item,
          id: item.id || `sec_${item.section_index || idx + 1}_${Date.now()}`,
          section_index: item.section_index || idx + 1,
          image_url: existingMap.get(item.section_index || idx + 1) || item.image_url,
          caption: item.caption || `图 ${item.section_index || idx + 1}：${item.section_title}`,
          prompt: item.prompt || item.prompt_zh || `${item.section_title} 极简商业概念摄影，暗调电影级光影质感，16:9 宽屏超清`,
        }))
      } else if (sectionIllustrations.value.length === 0) {
        const text = data?.content || props.content || ''
        sectionIllustrations.value = extractSectionsFromMarkdown(text)
      }
    }
  },
  { immediate: true }
)

const wechatRenderedHtml = computed(() => {
  const content = currentPlatformData.value?.content || props.content || ''
  const title = currentPlatformData.value?.title || props.title || ''
  if (!content) return ''
  return renderWechatHtmlWithDoocs(content, {
    theme: wechatDoocsTheme.value,
    title,
    author: authorName.value,
    illustrations: sectionIllustrations.value,
    enableFootnotes: true,
    includeHeaderInBody: includeHeaderInBody.value,
  })
})

async function handleGenerateSectionIllustration(slot: SectionIllustration) {
  if (!slot.prompt.trim() || slot.is_generating) return
  const slotId = slot.id || `sec_${slot.section_index}`
  generatingSectionId.value = slotId
  slot.is_generating = true

  try {
    const res = await generateAiImage({
      prompt: slot.prompt,
      platform: 'wechat',
      aspect_ratio: '16:9',
      style: wechatDoocsTheme.value,
      model: currentImageModel.value || 'agnes-image-2.5-flash',
    })
    slot.image_url = res.image_url
  } catch (err: any) {
    alert(err.message || '生成插图失败')
  } finally {
    slot.is_generating = false
    generatingSectionId.value = null
  }
}

async function handleGenerateAllIllustrations() {
  const slots = sectionIllustrations.value
  if (!slots.length || isGeneratingAllIllustrations.value) return

  isGeneratingAllIllustrations.value = true
  illustrationProgress.value = { current: 0, total: slots.length }

  for (let i = 0; i < slots.length; i++) {
    const slot = slots[i]
    illustrationProgress.value = { current: i + 1, total: slots.length }
    slot.is_generating = true
    try {
      const res = await generateAiImage({
        prompt: slot.prompt,
        platform: 'wechat',
        aspect_ratio: '16:9',
        style: wechatDoocsTheme.value,
        model: currentImageModel.value || 'agnes-image-2.5-flash',
      })
      slot.image_url = res.image_url
    } catch (err: any) {
      console.error(`Failed to generate illustration for section ${slot.section_index}:`, err)
    } finally {
      slot.is_generating = false
    }
  }

  isGeneratingAllIllustrations.value = false
}

async function handleCopySingleIllustration(slot: SectionIllustration) {
  if (!slot.image_url) return
  const slotKey = slot.id || `sec_${slot.section_index}`
  const success = await copySingleImageToClipboard(slot.image_url)
  if (success) {
    copiedSectionImgId.value = slotKey
    setTimeout(() => {
      if (copiedSectionImgId.value === slotKey) {
        copiedSectionImgId.value = null
      }
    }, 2500)
  }
}

async function handleCopyDoocsRichText() {
  if (!wechatRenderedHtml.value) return
  const plainText = includeHeaderInBody.value
    ? (currentPlatformData.value?.content || props.content)
    : undefined
  const success = await copyDoocsHtmlToClipboard(
    wechatRenderedHtml.value,
    plainText
  )
  if (success) {
    copiedDoocsRich.value = true
    copiedBody.value = true
    wechatAssistantToast.value = t.value.distribute.bodyCopiedToast
    setTimeout(() => {
      copiedDoocsRich.value = false
      copiedBody.value = false
      if (wechatAssistantToast.value === t.value.distribute.bodyCopiedToast) {
        wechatAssistantToast.value = null
      }
    }, 3500)
  }
}

async function downloadAllWechatAssetsAsZip() {
  if (isZippingWechat.value) return
  isZippingWechat.value = true
  zipWechatProgress.value = '正在收集微信排版素材...'

  try {
    const zip = new JSZip()
    const folderName = `微信公众号全套素材包_${(result.value?.title || '作品').slice(0, 15)}`
    const folder = zip.folder(folderName)

    if (wechatCover.value) {
      zipWechatProgress.value = '正在渲染微信头条标准大图 (900×383)...'
      const coverCanvas = renderWechatCoverToCanvas(wechatCover.value, selectedTheme.value)
      const coverBlob = await canvasToBlob(coverCanvas)
      folder?.file('00_微信头条官方大图封面_900x383.png', coverBlob)
    }

    if (wechatQuote.value) {
      zipWechatProgress.value = '正在渲染核心金句海报 (16:9)...'
      const quoteCanvas = renderWechatQuoteToCanvas(wechatQuote.value, selectedTheme.value)
      const quoteBlob = await canvasToBlob(quoteCanvas)
      folder?.file('01_正文金句高光配图_16x9.png', quoteBlob)
    }

    const slotsWithImg = sectionIllustrations.value.filter(s => !!s.image_url)
    for (let i = 0; i < slotsWithImg.length; i++) {
      const slot = slotsWithImg[i]
      zipWechatProgress.value = `正在打包第 ${i + 1}/${slotsWithImg.length} 张章节插图...`
      try {
        const img = new Image()
        img.crossOrigin = 'anonymous'
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve()
          img.onerror = () => reject()
          img.src = slot.image_url!
        })
        const canvas = document.createElement('canvas')
        canvas.width = img.naturalWidth || img.width
        canvas.height = img.naturalHeight || img.height
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(img, 0, 0)
          const blob = await canvasToBlob(canvas)
          const idxStr = String(slot.section_index || i + 1).padStart(2, '0')
          folder?.file(`插图_${idxStr}_${slot.section_title.slice(0, 12)}.png`, blob)
        }
      } catch (err) {
        console.warn('Failed to include illustration in zip:', err)
      }
    }

    if (wechatRenderedHtml.value) {
      const htmlFileContent = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${result.value?.title || '微信公众号排版'}</title>
</head>
<body>
${wechatRenderedHtml.value}
</body>
</html>`
      folder?.file('微信公众号已排版富文本(带内联样式直接复制).html', htmlFileContent)
    }

    const rawText = `${currentPlatformData.value?.title || result.value?.title || ''}\n\n${currentPlatformData.value?.content || props.content || ''}`
    folder?.file('文章Markdown原始内容.txt', rawText)

    zipWechatProgress.value = '正在极速压缩打包为 ZIP...'
    const zipBlob = await zip.generateAsync({ type: 'blob' })
    const zipFilename = `微信公众号全套素材包_${(result.value?.title || '作品').slice(0, 15)}.zip`
    const a = document.createElement('a')
    a.href = URL.createObjectURL(zipBlob)
    a.download = zipFilename
    a.click()
    a.remove()
  } catch (err: any) {
    alert(err.message || '打包微信素材失败')
  } finally {
    isZippingWechat.value = false
    zipWechatProgress.value = ''
  }
}

defineExpose({ downloadCurrentXhsCard })
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center glass-card-dark p-3 sm:p-6 overflow-y-auto">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-6xl max-h-[92vh] flex flex-col overflow-hidden toast-enter">
      
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/70 dark:bg-slate-800/40">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-xl shadow-xs border border-indigo-100 dark:border-indigo-900">
            🐟
          </div>
          <div>
            <h3 class="text-lg font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              {{ t.distribute.modalTitle }}
              <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 font-semibold">
                Windows Sandbox
              </span>
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {{ t.distribute.modalSubtitle }}
            </p>
          </div>
        </div>

        <button
          @click="closeModal"
          class="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 transition cursor-pointer"
          title="关闭"
        >
          ✕
        </button>
      </div>

      <!-- Platform Navigation Toolbar (Segmented Pills Control) -->
      <div class="px-6 py-3 border-b border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-slate-900/90 backdrop-blur-xs flex flex-wrap items-center justify-between gap-3 select-none">
        <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800/90 rounded-2xl gap-1 border border-slate-200/70 dark:border-slate-700/60 shadow-inner">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            :class="[
              'px-4 sm:px-5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center gap-2 cursor-pointer select-none',
              activeTab === tab.key
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200/80 dark:ring-slate-700'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-white/50 dark:hover:bg-slate-700/50'
            ]"
          >
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <!-- Right Side Platform Highlights / Badge -->
        <div class="hidden md:flex items-center gap-2">
          <span v-if="activeTab === 'xiaohongshu'" class="text-xs font-semibold px-3 py-1 rounded-full bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-900 flex items-center gap-1.5">
            <span>🎨</span>
            <span>{{ activeImageEngineLabel }} · 3:4 爆款卡片</span>
          </span>
          <span v-else-if="activeTab === 'wechat'" class="text-xs font-semibold px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900 flex items-center gap-1.5">
            <span>📰</span>
            <span>微信公众号 · 900×383 官方大图与金句</span>
          </span>
          <span v-else-if="activeTab === 'twitter'" class="text-xs font-semibold px-3 py-1 rounded-full bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300 border border-sky-200 dark:border-sky-900 flex items-center gap-1.5">
            <span>𝕏</span>
            <span>X (Twitter) · 连载 Thread 与互动转化</span>
          </span>
          <span v-else-if="activeTab === 'video'" class="text-xs font-semibold px-3 py-1 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-900 flex items-center gap-1.5">
            <span>🎬</span>
            <span>短视频口播 · 3秒黄金抓手与镜头提示</span>
          </span>
        </div>
      </div>

      <!-- Content Area -->
      <div class="flex-1 overflow-y-auto p-6 bg-slate-50/40 dark:bg-slate-950/20">
        <!-- Loading State -->
        <div v-if="loading" class="py-20 flex flex-col items-center justify-center text-center">
          <div class="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
          <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {{ t.distribute.formatting }}
          </p>
          <span class="text-xs text-slate-400 mt-1">Calling content_multi_distributor inside Windows Sandbox...</span>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="p-5 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-400 text-sm space-y-2">
          <p class="font-bold flex items-center gap-1.5">
            <span>⚠️</span>
            <span>分发排版失败</span>
          </p>
          <p class="text-xs">{{ error }}</p>
          <button @click="fetchDistribution" class="text-xs px-4 py-1.5 bg-rose-600 text-white font-bold rounded-xl hover:bg-rose-700 transition cursor-pointer">
            重新尝试
          </button>
        </div>

        <!-- Loaded Data Display -->
        <div v-else-if="currentPlatformData" class="space-y-6">
          
          <!-- Top Bar: Title + Theme Selector + Copy Action -->
          <div class="flex flex-wrap items-center justify-between gap-4 bg-white dark:bg-slate-800 p-4 sm:p-5 rounded-2xl border border-slate-200/80 dark:border-slate-700 shadow-sm">
            <div class="flex-1 min-w-[240px]">
              <h4 class="text-base sm:text-lg font-extrabold text-slate-900 dark:text-slate-100 break-words leading-snug">
                {{ currentPlatformData.title || result?.title }}
              </h4>
              <div v-if="activeTab === 'video' && currentPlatformData.estimated_duration_seconds" class="mt-1 flex items-center gap-2">
                <span class="text-xs font-bold px-2.5 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                  ⏱️ {{ t.distribute.duration.replace('{sec}', currentPlatformData.estimated_duration_seconds.toString()) }}
                </span>
              </div>
            </div>

            <!-- WeChat doocs/md Theme Picker -->
            <div v-if="activeTab === 'wechat' && wechatMode === 'layout'" class="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-700/60 p-1.5 rounded-xl text-xs font-semibold">
              <span class="text-slate-500 px-1.5 text-[11px]">{{ t.distribute.doocsThemeLabel }}</span>
              <button
                v-for="th in Object.values(DOOCS_THEMES)"
                :key="th.id"
                @click="wechatDoocsTheme = th.id"
                :class="[
                  'px-2.5 py-1 rounded-lg transition cursor-pointer flex items-center gap-1 text-xs',
                  wechatDoocsTheme === th.id
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-bold shadow-xs ring-1 ring-slate-300 dark:ring-slate-600'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'
                ]"
              >
                <span>{{ th.emoji }}</span>
                <span>{{ th.nameZh }}</span>
              </button>
            </div>

            <!-- Card Visual Theme Picker for Xiaohongshu and WeChat Visual Poster -->
            <div v-else-if="activeTab === 'xiaohongshu' || (activeTab === 'wechat' && wechatMode === 'visual')" class="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-700/60 p-1.5 rounded-xl text-xs font-semibold">
              <span class="text-slate-500 px-1.5 text-[11px]">{{ t.distribute.themeLabel }}</span>
              <button
                @click="selectedTheme = 'dark_gold'"
                :class="['px-3 py-1.5 rounded-lg transition cursor-pointer', selectedTheme === 'dark_gold' ? 'bg-slate-900 text-amber-300 font-bold shadow-xs' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900']"
              >
                {{ t.distribute.themeDarkGold }}
              </button>
              <button
                @click="selectedTheme = 'indigo_purple'"
                :class="['px-3 py-1.5 rounded-lg transition cursor-pointer', selectedTheme === 'indigo_purple' ? 'bg-indigo-900 text-sky-300 font-bold shadow-xs' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900']"
              >
                {{ t.distribute.themeIndigo }}
              </button>
              <button
                @click="selectedTheme = 'clean_minimal'"
                :class="['px-3 py-1.5 rounded-lg transition cursor-pointer', selectedTheme === 'clean_minimal' ? 'bg-white text-blue-700 font-bold shadow-xs' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900']"
              >
                {{ t.distribute.themeClean }}
              </button>
            </div>

            <!-- Action Button for WeChat Rich Text Copy -->
            <button
              v-if="activeTab === 'wechat' && wechatMode === 'layout'"
              @click="handleCopyDoocsRichText"
              :class="[
                'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition shadow-sm shrink-0 cursor-pointer active:scale-95',
                copiedDoocsRich
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-emerald-500/20'
              ]"
            >
              <span>{{ copiedDoocsRich ? '✓' : '📋' }}</span>
              <span>{{ copiedDoocsRich ? '✓ 微信带图富文本已复制 (可直接粘贴微信后台)' : '一键复制带图富文本 (直粘微信后台)' }}</span>
            </button>

            <!-- Standard Copy button for text -->
            <button
              v-else
              @click="copyText(currentPlatformData.content, activeTab)"
              :class="[
                'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition shadow-sm shrink-0 cursor-pointer active:scale-95',
                copiedPlatform === activeTab
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white'
              ]"
            >
              <span>{{ copiedPlatform === activeTab ? '✓' : '📋' }}</span>
              <span>{{ copiedPlatform === activeTab ? t.distribute.copySuccess : t.distribute.copyBtn }}</span>
            </button>
          </div>

          <!-- ========================================== -->
          <!-- 1. XIAOHONGSHU TAB (Spacious 2-Column Grid) -->
          <!-- ========================================== -->
          <div v-if="activeTab === 'xiaohongshu'" class="space-y-4">
            <!-- Mode Switcher Tabs -->
            <div class="flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
              <button
                @click="xhsMode = 'cards'"
                :class="[
                  'px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer',
                  xhsMode === 'cards'
                    ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 border border-slate-200 dark:border-slate-700'
                ]"
              >
                <span>{{ t.distribute.tabVisualCards }}</span>
                <span v-if="xhsCards.length" class="text-[11px] bg-white/25 px-1.5 py-0.2 rounded-full font-black">
                  {{ xhsCards.length }}
                </span>
              </button>
              <button
                @click="xhsMode = 'copy'"
                :class="[
                  'px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer',
                  xhsMode === 'copy'
                    ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 border border-slate-200 dark:border-slate-700'
                ]"
              >
                <span>{{ t.distribute.tabCopywriting }}</span>
              </button>

              <!-- Module 5: Card Layout View Mode Switcher -->
              <div v-if="xhsMode === 'cards'" class="ml-auto flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-semibold">
                <button
                  type="button"
                  @click="xhsCardViewMode = 'carousel'"
                  :class="['px-3 py-1 rounded-lg transition cursor-pointer flex items-center gap-1', xhsCardViewMode === 'carousel' ? 'bg-white dark:bg-slate-700 text-rose-600 dark:text-rose-400 shadow-xs font-bold' : 'text-slate-500 hover:text-slate-800']"
                >
                  <span>📱</span>
                  <span>单卡精修轮播</span>
                </button>
                <button
                  type="button"
                  @click="xhsCardViewMode = 'grid'"
                  :class="['px-3 py-1 rounded-lg transition cursor-pointer flex items-center gap-1', xhsCardViewMode === 'grid' ? 'bg-white dark:bg-slate-700 text-rose-600 dark:text-rose-400 shadow-xs font-bold' : 'text-slate-500 hover:text-slate-800']"
                >
                  <span>🖼️</span>
                  <span>九宫格总览模式</span>
                </button>
              </div>
            </div>

            <!-- Module 5: Sub-view A1: Nine-Grid Overview Mode -->
            <div v-if="xhsMode === 'cards' && xhsCards.length && xhsCardViewMode === 'grid'" class="space-y-4">
              <div class="flex items-center justify-between flex-wrap gap-3 bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm">
                <div>
                  <div class="flex items-center gap-2">
                    <h5 class="text-xs font-black text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                      小红书全套卡片九宫格总览 (共 {{ xhsCards.length }} 张卡片)
                    </h5>
                    <span class="text-[10px] bg-rose-100 dark:bg-rose-900 text-rose-700 dark:text-rose-300 font-bold px-2.5 py-0.5 rounded-full border border-rose-200 dark:border-rose-800">
                      3:4 竖版高分辨率
                    </span>
                  </div>
                  <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    当前视觉主题：<span class="font-bold text-amber-500">{{ selectedTheme === 'dark_gold' ? '深邃黑金' : selectedTheme === 'indigo_purple' ? '极简幻紫' : '清爽白瓷' }}</span> · 点击任意卡片可进入精修模式
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    @click="downloadAllXhsCardsAsZip"
                    :disabled="isZippingAll"
                    class="px-4 py-2 bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-700 hover:to-pink-700 disabled:opacity-50 text-white rounded-xl font-bold text-xs transition flex items-center gap-1.5 cursor-pointer shadow-md shadow-rose-500/20 active:scale-95"
                    title="打包下载包含全部 3:4 超清卡片 (1080×1440) + 小红书文案标签"
                  >
                    <span>📦</span>
                    <span>{{ isZippingAll ? zipProgress : '一键打包下载全部卡片 (ZIP)' }}</span>
                  </button>
                </div>
              </div>

              <!-- Nine-Grid Canvas Preview -->
              <!-- Each <img> is a data URL from the SAME Canvas renderer used for download.
                   Preview == Download, always. No second HTML layout to maintain. -->
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                <div
                  v-for="(card, idx) in xhsCards"
                  :key="idx"
                  class="aspect-[3/4] relative overflow-hidden rounded-2xl shadow-xl cursor-pointer select-none group"
                  :class="activeXhsCardIdx === idx ? 'ring-2 ring-rose-500' : 'ring-1 ring-slate-700/40'"
                  @click="activeXhsCardIdx = idx; xhsCardViewMode = 'carousel'"
                  :title="`点击进入精修：${card.title}`"
                >
                  <!-- Canvas preview image (pixel-identical to download) -->
                  <img
                    v-if="xhsPreviewImages[idx]"
                    :src="xhsPreviewImages[idx]"
                    class="absolute inset-0 w-full h-full object-cover"
                    :alt="`卡片 ${idx + 1}`"
                    draggable="false"
                  />

                  <!-- Loading skeleton while canvas renders -->
                  <div
                    v-else
                    class="absolute inset-0 flex flex-col items-center justify-center gap-2"
                    :class="selectedTheme === 'dark_gold'
                      ? 'bg-gradient-to-br from-slate-900 to-indigo-950'
                      : selectedTheme === 'indigo_purple'
                      ? 'bg-gradient-to-br from-indigo-950 to-purple-900'
                      : 'bg-gradient-to-br from-slate-100 to-white'"
                  >
                    <div class="w-6 h-6 border-2 border-rose-500 border-t-transparent rounded-full animate-spin"></div>
                    <span class="text-[10px] text-white/50">渲染中…</span>
                  </div>

                  <!-- Hover overlay with actions -->
                  <div class="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-2 bg-black/70 backdrop-blur-sm translate-y-full group-hover:translate-y-0 transition-transform duration-200">
                    <span class="text-[10px] font-bold text-white/70">{{ card.card_type === 'cover' ? '封面' : card.card_type === 'summary' ? '总结' : `要点 ${idx}` }}</span>
                    <button
                      type="button"
                      @click.stop="activeXhsCardIdx = idx; downloadCurrentXhsCard()"
                      class="px-2.5 py-1 rounded-lg bg-white/15 hover:bg-white/30 text-[10px] font-bold text-white transition flex items-center gap-1 cursor-pointer"
                      title="下载此张 1080×1440 高清卡片"
                    >
                      <span>📸</span>
                      <span>PNG</span>
                    </button>
                  </div>
                </div>
              </div><!-- end grid -->
            </div><!-- end nine-grid section -->


            <!-- Sub-view A2: Visual Cards with 2-Column Responsive Layout (Carousel Mode) -->
            <div v-if="xhsMode === 'cards' && xhsCards.length && xhsCardViewMode === 'carousel'" class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              
              <!-- LEFT COLUMN: AI Image Console & Download Actions (5 cols) -->
              <div class="lg:col-span-5 space-y-4">
                
                <!-- AI Image Generation Panel -->
                <div class="bg-gradient-to-br from-rose-50/80 via-white to-purple-50/60 dark:from-rose-950/30 dark:via-slate-900 dark:to-purple-950/30 p-5 rounded-2xl border border-rose-200/80 dark:border-rose-900/60 shadow-sm space-y-4">
                  <div class="flex items-center justify-between flex-wrap gap-2">
                    <div class="flex items-center gap-2">
                      <span class="text-base">🎨</span>
                      <h5 class="text-xs font-black text-rose-800 dark:text-rose-200">
                        {{ t.distribute.aiImageSectionTitle }}
                      </h5>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <span class="text-[10px] px-2.5 py-0.5 rounded-full bg-gradient-to-r from-rose-600 to-pink-600 text-white font-black shadow-xs flex items-center gap-1">
                        <span>✨</span>
                        <span>{{ activeImageEngineLabel }}</span>
                      </span>
                      <span class="text-[10px] px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 font-bold border border-rose-200 dark:border-rose-800">
                        3:4 商业首图
                      </span>
                    </div>
                  </div>

                  <!-- Prompt input & generate -->
                  <div class="space-y-2">
                    <label class="block text-[11px] font-bold text-slate-600 dark:text-slate-300">
                      {{ t.distribute.aiImagePromptLabel }}
                    </label>
                    <textarea
                      v-model="aiImagePrompt"
                      rows="3"
                      :placeholder="t.distribute.aiImagePromptPlaceholder"
                      class="w-full px-3.5 py-2.5 text-xs rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500 shadow-xs"
                      @keydown.ctrl.enter="handleGenerateAiImage"
                    ></textarea>

                    <button
                      @click="handleGenerateAiImage"
                      :disabled="isGeneratingAiImage || !aiImagePrompt.trim()"
                      class="w-full py-2.5 bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-700 hover:to-pink-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition shadow-md shadow-rose-500/20 flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                    >
                      <span v-if="isGeneratingAiImage" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                      <span v-else>🎨</span>
                      <span>{{ isGeneratingAiImage ? t.distribute.aiImageGenerating : t.distribute.aiImageGenerateBtn }}</span>
                    </button>
                  </div>

                  <!-- Feedback Notifications -->
                  <div v-if="aiImageSuccess" class="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 font-semibold bg-emerald-50 dark:bg-emerald-950/40 p-2.5 rounded-xl border border-emerald-200 dark:border-emerald-800">
                    <span>✅</span>
                    <span>{{ t.distribute.aiImageGeneratedSuccess }}</span>
                  </div>
                  <div v-if="aiImageError" class="text-xs text-rose-600 dark:text-rose-400 font-medium bg-rose-50 dark:bg-rose-950/40 p-2.5 rounded-xl border border-rose-200">
                    {{ aiImageError }}
                  </div>
                  <div v-if="aiImageUrl && isFallbackAiImage" class="text-[11px] text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 p-2.5 rounded-xl border border-amber-200 dark:border-amber-800 leading-relaxed space-y-1">
                    <div class="flex items-center gap-1.5 font-bold">
                      <span>💡</span>
                      <span>{{ t.distribute.aiImageFallbackHint }}</span>
                    </div>
                    <p class="text-[10px] text-amber-700 dark:text-amber-400">
                      {{ t.distribute.configKeyTip }}
                    </p>
                  </div>

                  <!-- Preview mode switch (when AI image is generated) -->
                  <div v-if="aiImageUrl" class="pt-2 border-t border-rose-100 dark:border-rose-900/40 flex items-center justify-between">
                    <span class="text-xs font-semibold text-slate-500">首图预览视图：</span>
                    <div class="flex items-center gap-1 bg-white dark:bg-slate-800 p-1 rounded-xl border border-rose-200/80 dark:border-rose-900">
                      <button
                        @click="aiImagePreviewMode = 'composite'"
                        :class="['px-3 py-1 rounded-lg transition cursor-pointer text-xs font-bold', aiImagePreviewMode === 'composite' ? 'bg-rose-600 text-white shadow-xs' : 'text-slate-600 dark:text-slate-300']"
                      >
                        {{ t.distribute.previewComposite }}
                      </button>
                      <button
                        @click="aiImagePreviewMode = 'pure'"
                        :class="['px-3 py-1 rounded-lg transition cursor-pointer text-xs font-bold', aiImagePreviewMode === 'pure' ? 'bg-rose-600 text-white shadow-xs' : 'text-slate-600 dark:text-slate-300']"
                      >
                        {{ t.distribute.previewPureBg }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Export & Batch Download Actions Box -->
                <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-2.5">
                  <div class="text-xs font-extrabold text-slate-700 dark:text-slate-200 uppercase tracking-wider mb-2">
                    📦 卡片导出与下载选项
                  </div>
                  
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <button
                      @click="downloadCurrentXhsCard"
                      class="px-3 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100 rounded-xl font-bold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>📸</span>
                      <span>下载当前第 {{ activeXhsCardIdx + 1 }} 页</span>
                    </button>

                    <button
                      @click="downloadCompositeCoverImage"
                      class="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-xl font-bold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>🖼️</span>
                      <span>下载大字报合成首图</span>
                    </button>

                    <button
                      @click="downloadPureAiBackground"
                      :disabled="!aiImageUrl"
                      class="px-3 py-2 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-40 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-xl font-bold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>🎨</span>
                      <span>下载纯净 AI 背景图</span>
                    </button>

                    <button
                      @click="downloadAllXhsCards"
                      :disabled="isDownloadingAll"
                      class="px-3 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-xl font-bold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
                    >
                      <span>📦</span>
                      <span>{{ isDownloadingAll ? (locale === 'zh' ? '正在打包...' : 'Packaging...') : t.distribute.batchDownloadAllCards }}</span>
                    </button>
                  </div>
                </div>

                <!-- Card Thumbnails Navigation Strip -->
                <div class="bg-white dark:bg-slate-800 p-3.5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-2">
                  <div class="flex items-center justify-between text-xs font-semibold text-slate-500">
                    <span>卡片页码快速跳转：</span>
                    <span class="text-indigo-600 font-bold">{{ activeXhsCardIdx + 1 }} / {{ xhsCards.length }}</span>
                  </div>
                  <div class="flex items-center gap-2 overflow-x-auto p-1">
                    <button
                      v-for="(c, cidx) in xhsCards"
                      :key="cidx"
                      @click="activeXhsCardIdx = cidx"
                      :class="[
                        'w-14 h-18 rounded-xl border-2 transition overflow-hidden text-[10px] p-1.5 flex flex-col justify-between shrink-0 cursor-pointer shadow-xs',
                        activeXhsCardIdx === cidx
                          ? 'border-rose-500 shadow-md scale-105 bg-rose-50 dark:bg-rose-950/60 font-black text-rose-700'
                          : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 opacity-70 hover:opacity-100'
                      ]"
                    >
                      <span class="font-bold truncate">{{ c.card_type === 'cover' ? 'P1 封面' : `P${cidx + 1} 内页` }}</span>
                      <span class="text-[9px] opacity-70 truncate leading-tight">{{ c.title }}</span>
                    </button>
                  </div>
                </div>

              </div>

              <!-- RIGHT COLUMN: Canvas Preview (pixel-identical to download) -->
              <div class="lg:col-span-7 flex flex-col items-center justify-center p-6 bg-slate-100/70 dark:bg-slate-950/40 rounded-3xl border border-slate-200 dark:border-slate-800">

                <!-- Canvas preview img — same render path as download -->
                <div class="w-[330px] sm:w-[370px] md:w-[385px] aspect-[3/4] relative rounded-3xl shadow-2xl overflow-hidden border-2 border-slate-700/30">
                  <img
                    v-if="xhsCarouselPreviewImage"
                    :src="xhsCarouselPreviewImage"
                    class="w-full h-full object-cover"
                    alt="卡片预览"
                    draggable="false"
                  />
                  <!-- Render loading state -->
                  <div
                    v-else
                    class="absolute inset-0 flex flex-col items-center justify-center gap-3"
                    :class="selectedTheme === 'dark_gold'
                      ? 'bg-gradient-to-br from-slate-900 to-indigo-950'
                      : selectedTheme === 'indigo_purple'
                      ? 'bg-gradient-to-br from-indigo-950 to-purple-900'
                      : 'bg-gradient-to-br from-slate-100 to-white'"
                  >
                    <div class="w-7 h-7 border-2 border-rose-500 border-t-transparent rounded-full animate-spin"></div>
                    <span class="text-xs text-white/50 font-medium">渲染预览中…</span>
                  </div>
                </div>

                <!-- Carousel Controls -->
                <div class="flex items-center gap-4 mt-5">
                  <button
                    @click="activeXhsCardIdx = Math.max(0, activeXhsCardIdx - 1)"
                    :disabled="activeXhsCardIdx === 0"
                    class="px-3.5 py-1.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-30 hover:bg-slate-50 transition shadow-sm font-bold text-sm cursor-pointer"
                  >
                    ← 上一页
                  </button>
                  <span class="text-xs font-bold text-slate-700 dark:text-slate-200">
                    第 {{ activeXhsCardIdx + 1 }} / {{ xhsCards.length }} 页
                  </span>
                  <button
                    @click="activeXhsCardIdx = Math.min(xhsCards.length - 1, activeXhsCardIdx + 1)"
                    :disabled="activeXhsCardIdx === xhsCards.length - 1"
                    class="px-3.5 py-1.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-30 hover:bg-slate-50 transition shadow-sm font-bold text-sm cursor-pointer"
                  >
                    下一页 →
                  </button>
                </div>

              </div>

            </div>



            <!-- Sub-view B: Copywriting Text & Tags -->
            <div v-if="xhsMode === 'copy' || !xhsCards.length" class="space-y-4">
              <div v-if="currentPlatformData.tags && currentPlatformData.tags.length" class="flex flex-wrap gap-2 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700">
                <span class="text-xs font-bold text-slate-500 self-center">{{ t.distribute.tags }}:</span>
                <span
                  v-for="tag in currentPlatformData.tags"
                  :key="tag"
                  class="text-xs px-3 py-1 rounded-full bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900 font-semibold"
                >
                  {{ tag }}
                </span>
              </div>

              <div class="bg-white dark:bg-slate-800 p-6 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm text-sm leading-relaxed whitespace-pre-wrap font-sans text-slate-800 dark:text-slate-200">
                {{ currentPlatformData.content }}
              </div>
            </div>
          </div>

          <!-- ========================================== -->
          <!-- 2. WECHAT OFFICIAL TAB (doocs/md + Visuals) -->
          <!-- ========================================== -->
          <div v-else-if="activeTab === 'wechat'" class="space-y-5">
            <!-- WeChat Mode Switcher -->
            <div class="flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3 flex-wrap">
              <button
                @click="wechatMode = 'layout'"
                :class="[
                  'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer',
                  wechatMode === 'layout'
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 border border-slate-200 dark:border-slate-700'
                ]"
              >
                <span>{{ t.distribute.tabWechatLayout }}</span>
                <span v-if="sectionIllustrations.length" class="text-[11px] bg-white/25 px-1.5 py-0.2 rounded-full font-black">
                  {{ sectionIllustrations.length }} 插图
                </span>
              </button>

              <button
                @click="wechatMode = 'visual'"
                :class="[
                  'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer',
                  wechatMode === 'visual'
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 border border-slate-200 dark:border-slate-700'
                ]"
              >
                <span>{{ t.distribute.tabWechatVisual }}</span>
              </button>

              <button
                @click="wechatMode = 'text'"
                :class="[
                  'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer',
                  wechatMode === 'text'
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 border border-slate-200 dark:border-slate-700'
                ]"
              >
                <span>{{ t.distribute.tabWechatRaw }}</span>
              </button>

              <!-- Quick Zip Download Shortcut -->
              <button
                v-if="wechatMode === 'layout'"
                @click="downloadAllWechatAssetsAsZip"
                :disabled="isZippingWechat"
                class="ml-auto px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <span>📦</span>
                <span>{{ isZippingWechat ? zipWechatProgress : t.distribute.batchDownloadWechatZip }}</span>
              </button>
            </div>

            <!-- ============================================ -->
            <!-- SUB-VIEW 1: doocs/md Layout & AI Illustration Studio -->
            <!-- ============================================ -->
            <div v-if="wechatMode === 'layout'" class="space-y-5">

              <!-- WeChat MP Title & Author Publishing Assistant (3-Step Toolbar) -->
              <div class="bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-emerald-500/5 dark:from-emerald-950/40 dark:via-teal-950/30 dark:to-slate-900 p-4 sm:p-5 rounded-2xl border border-emerald-300/70 dark:border-emerald-700/60 shadow-xs space-y-3">
                <div class="flex items-center justify-between flex-wrap gap-2">
                  <div class="flex items-center gap-2">
                    <span class="text-base sm:text-lg">🚀</span>
                    <h5 class="text-xs sm:text-sm font-extrabold text-emerald-900 dark:text-emerald-200">
                      {{ t.distribute.wechatPublishAssistant }}
                    </h5>
                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/80 text-emerald-800 dark:text-emerald-300 font-bold border border-emerald-200 dark:border-emerald-700">
                      {{ t.distribute.wechatStepBadge }}
                    </span>
                  </div>

                  <!-- Include Title & Author Toggle Checkbox -->
                  <label class="inline-flex items-center gap-2 cursor-pointer select-none text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white/80 dark:bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-200/80 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 transition" :title="t.distribute.includeHeaderHint">
                    <input
                      type="checkbox"
                      v-model="includeHeaderInBody"
                      class="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 w-4 h-4 cursor-pointer"
                    />
                    <span>{{ t.distribute.includeHeaderToggle }}</span>
                  </label>
                </div>

                <!-- 3 Steps Grid -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <!-- Step 1: Article Title -->
                  <div class="bg-white dark:bg-slate-800/90 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700 shadow-xs flex flex-col justify-between space-y-2">
                    <div class="space-y-1">
                      <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-slate-400">
                        <span class="flex items-center gap-1">
                          <span class="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-900/80 text-emerald-700 dark:text-emerald-300 text-[10px] font-black inline-flex items-center justify-center">1</span>
                          <span>{{ t.distribute.wechatStep1 }}</span>
                        </span>
                        <span class="text-[10px] opacity-75">{{ t.distribute.wechatTargetTitleBar }}</span>
                      </div>
                      <p class="text-xs font-bold text-slate-900 dark:text-slate-100 line-clamp-2 min-h-[32px] break-words" :title="articleTitle">
                        {{ articleTitle || t.distribute.noTitlePlaceholder }}
                      </p>
                    </div>
                    <button
                      type="button"
                      @click="handleCopyTitle"
                      :class="[
                        'w-full py-1.5 px-3 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow-xs active:scale-95',
                        copiedTitle
                          ? 'bg-emerald-600 text-white'
                          : 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/60 dark:hover:bg-emerald-900 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                      ]"
                    >
                      <span>{{ copiedTitle ? '✓' : '📋' }}</span>
                      <span>{{ copiedTitle ? t.distribute.titleCopiedBtn : t.distribute.copyTitleBtn }}</span>
                    </button>
                  </div>

                  <!-- Step 2: Author -->
                  <div class="bg-white dark:bg-slate-800/90 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700 shadow-xs flex flex-col justify-between space-y-2">
                    <div class="space-y-1">
                      <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-slate-400">
                        <span class="flex items-center gap-1">
                          <span class="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-900/80 text-emerald-700 dark:text-emerald-300 text-[10px] font-black inline-flex items-center justify-center">2</span>
                          <span>{{ t.distribute.wechatStep2 }}</span>
                        </span>
                        <span class="text-[10px] opacity-75">{{ t.distribute.wechatTargetAuthorBar }}</span>
                      </div>
                      <p class="text-xs font-bold text-slate-900 dark:text-slate-100 line-clamp-2 min-h-[32px] break-words" :title="authorName">
                        {{ authorName }}
                      </p>
                    </div>
                    <button
                      type="button"
                      @click="handleCopyAuthor"
                      :class="[
                        'w-full py-1.5 px-3 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow-xs active:scale-95',
                        copiedAuthor
                          ? 'bg-emerald-600 text-white'
                          : 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/60 dark:hover:bg-emerald-900 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                      ]"
                    >
                      <span>{{ copiedAuthor ? '✓' : '📋' }}</span>
                      <span>{{ copiedAuthor ? t.distribute.authorCopiedBtn : t.distribute.copyAuthorBtn }}</span>
                    </button>
                  </div>

                  <!-- Step 3: Formatted Body -->
                  <div class="bg-white dark:bg-slate-800/90 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700 shadow-xs flex flex-col justify-between space-y-2">
                    <div class="space-y-1">
                      <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-slate-400">
                        <span class="flex items-center gap-1">
                          <span class="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-900/80 text-emerald-700 dark:text-emerald-300 text-[10px] font-black inline-flex items-center justify-center">3</span>
                          <span>{{ t.distribute.wechatStep3 }}</span>
                        </span>
                        <span class="text-[10px] opacity-75">{{ t.distribute.wechatTargetBodyEditor }}</span>
                      </div>
                      <p class="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 min-h-[32px]">
                        {{ includeHeaderInBody ? t.distribute.bodyDescWithHeader : t.distribute.bodyDescClean }}
                      </p>
                    </div>
                    <button
                      type="button"
                      @click="handleCopyDoocsRichText"
                      :class="[
                        'w-full py-1.5 px-3 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-emerald-500/20 active:scale-95 text-white',
                        copiedDoocsRich
                          ? 'bg-emerald-700'
                          : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700'
                      ]"
                    >
                      <span>{{ copiedDoocsRich ? '✓' : '📋' }}</span>
                      <span>{{ copiedDoocsRich ? t.distribute.bodyCopiedBtn : t.distribute.copyBodyBtn }}</span>
                    </button>
                  </div>
                </div>

                <!-- Toast Notification Banner -->
                <div v-if="wechatAssistantToast" class="p-2.5 rounded-xl bg-emerald-600 text-white text-xs font-bold flex items-center justify-between shadow-sm animate-in fade-in duration-200">
                  <div class="flex items-center gap-2">
                    <span>🎉</span>
                    <span>{{ wechatAssistantToast }}</span>
                  </div>
                  <button type="button" @click="wechatAssistantToast = null" class="opacity-80 hover:opacity-100 cursor-pointer text-xs">
                    ✕
                  </button>
                </div>
              </div>

              <!-- Top Banner & Quick Copy Action -->
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gradient-to-r from-emerald-50/80 via-white to-teal-50/60 dark:from-emerald-950/30 dark:via-slate-900 dark:to-teal-950/30 p-5 rounded-2xl border border-emerald-200/80 dark:border-emerald-900/60 shadow-sm">
                <div class="space-y-1">
                  <h5 class="text-xs font-black text-emerald-900 dark:text-emerald-200 uppercase tracking-wide flex items-center gap-2">
                    <span>📰</span>
                    <span>{{ t.distribute.wechatLayoutTitle }}</span>
                    <span class="text-[10px] px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-900/80 text-emerald-800 dark:text-emerald-300 font-bold border border-emerald-200 dark:border-emerald-700">
                      doocs/md 渲染内核 · 100% 行内样式
                    </span>
                  </h5>
                  <p class="text-xs text-slate-600 dark:text-slate-400">
                    {{ t.distribute.wechatLayoutDesc }}
                  </p>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    @click="handleCopyDoocsRichText"
                    class="px-4 py-2.5 rounded-xl text-xs font-bold transition shadow-md flex items-center gap-1.5 cursor-pointer active:scale-95"
                    :class="copiedDoocsRich ? 'bg-emerald-600 text-white' : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-emerald-500/20'"
                  >
                    <span>{{ copiedDoocsRich ? '✓' : '📋' }}</span>
                    <span>{{ copiedDoocsRich ? '✓ 微信富文本已复制 (可直接粘贴后台)' : t.distribute.copyWechatRichBtn }}</span>
                  </button>
                </div>
              </div>

              <!-- Two-Column Responsive Workspace -->
              <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                
                <!-- LEFT COLUMN: Section Illustrations Console (5 Cols) -->
                <div class="lg:col-span-5 space-y-4">
                  <div class="bg-white dark:bg-slate-800 p-5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
                    <div class="flex items-center justify-between flex-wrap gap-2">
                      <div class="flex items-center gap-2">
                        <span class="text-base">🎨</span>
                        <h5 class="text-xs font-black text-slate-800 dark:text-slate-200">
                          {{ t.distribute.illustrationsTitle }}
                        </h5>
                        <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300 font-bold">
                          {{ sectionIllustrations.length }} 个小节
                        </span>
                      </div>
                      <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-bold">
                        16:9 宽屏
                      </span>
                    </div>

                    <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                      {{ t.distribute.illustrationsDesc }}
                    </p>

                    <!-- Batch Generate Button -->
                    <button
                      type="button"
                      @click="handleGenerateAllIllustrations"
                      :disabled="isGeneratingAllIllustrations || !sectionIllustrations.length"
                      class="w-full py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition shadow-md shadow-emerald-500/20 flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                    >
                      <span v-if="isGeneratingAllIllustrations" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                      <span v-else>🚀</span>
                      <span>{{ isGeneratingAllIllustrations ? t.distribute.generatingAllIllustrations.replace('{current}', illustrationProgress.current.toString()).replace('{total}', illustrationProgress.total.toString()) : t.distribute.generateAllIllustrations }}</span>
                    </button>
                  </div>

                  <!-- Slot Cards List -->
                  <div class="space-y-3">
                    <div
                      v-for="(slot, sIdx) in sectionIllustrations"
                      :key="slot.id || sIdx"
                      class="p-4 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-3"
                    >
                      <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                          <span class="w-5 h-5 rounded-md bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300 text-[10px] font-black flex items-center justify-center">
                            {{ slot.section_index || sIdx + 1 }}
                          </span>
                          <h6 class="text-xs font-black text-slate-800 dark:text-slate-200 line-clamp-1">
                            {{ slot.section_title }}
                          </h6>
                        </div>
                        <span v-if="slot.image_url" class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400 font-bold border border-emerald-200 dark:border-emerald-800">
                          ✓ 已就绪
                        </span>
                      </div>

                      <!-- Prompt Edit Box -->
                      <div class="space-y-1">
                        <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400">
                          {{ t.distribute.illustrationPromptLabel }}
                        </label>
                        <textarea
                          v-model="slot.prompt"
                          rows="2"
                          class="w-full px-3 py-1.5 text-xs rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          placeholder="输入生图画面描述..."
                        ></textarea>
                      </div>

                      <!-- Illustration Preview or Action Box -->
                      <div v-if="slot.image_url" class="space-y-2">
                        <div class="relative rounded-xl overflow-hidden aspect-[16/9] border border-slate-200 dark:border-slate-700 bg-slate-900 shadow-inner group">
                          <img
                            :src="slot.image_url"
                            :alt="slot.caption || slot.section_title"
                            class="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                          />
                          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2 p-2">
                            <button
                              type="button"
                              @click="handleCopySingleIllustration(slot)"
                              class="px-2.5 py-1 bg-white/90 hover:bg-white text-slate-900 text-[11px] font-bold rounded-lg transition shadow-xs cursor-pointer"
                            >
                              {{ copiedSectionImgId === (slot.id || `sec_${slot.section_index}`) ? '✓ 已复制' : '📋 复制' }}
                            </button>
                            <button
                              type="button"
                              @click="downloadImageFromUrl(slot.image_url, `公众号插图_${slot.section_index}_${slot.section_title.slice(0, 10)}`)"
                              class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold rounded-lg transition shadow-xs cursor-pointer"
                            >
                              📸 下载
                            </button>
                            <button
                              type="button"
                              @click="handleGenerateSectionIllustration(slot)"
                              :disabled="slot.is_generating"
                              class="px-2.5 py-1 bg-slate-800/90 hover:bg-slate-800 text-white text-[11px] font-bold rounded-lg transition shadow-xs cursor-pointer disabled:opacity-50"
                            >
                              🔄 重生
                            </button>
                          </div>
                        </div>
                        <p class="text-[10px] text-center text-slate-500 italic">
                          {{ slot.caption }}
                        </p>
                      </div>

                      <div v-else class="pt-1">
                        <button
                          type="button"
                          @click="handleGenerateSectionIllustration(slot)"
                          :disabled="slot.is_generating"
                          class="w-full py-2 bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                        >
                          <span v-if="slot.is_generating" class="w-3.5 h-3.5 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin"></span>
                          <span v-else>🎨</span>
                          <span>{{ slot.is_generating ? t.distribute.generatingSectionIllustration : t.distribute.generateSectionIllustration }}</span>
                        </button>
                      </div>

                    </div>
                  </div>
                </div>

                <!-- RIGHT COLUMN: Real-Time WYSIWYG Article Preview (7 Cols) -->
                <div class="lg:col-span-7 space-y-3">
                  <!-- Preview Header Bar -->
                  <div class="flex items-center justify-between bg-white dark:bg-slate-800 p-3.5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-xs">
                    <div class="flex items-center gap-2">
                      <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      <h6 class="text-xs font-black text-slate-800 dark:text-slate-200">
                        {{ t.distribute.previewWechatTitle }}
                      </h6>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <span class="text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
                        <span>{{ DOOCS_THEMES[wechatDoocsTheme].emoji }}</span>
                        <span>{{ DOOCS_THEMES[wechatDoocsTheme].nameZh }}</span>
                      </span>
                      <button
                        type="button"
                        @click="handleCopyDoocsRichText"
                        class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold transition cursor-pointer shadow-xs"
                      >
                        {{ copiedDoocsRich ? '✓ 已复制' : '📋 复制' }}
                      </button>
                    </div>
                  </div>

                  <!-- Mobile / Desktop Simulation Box -->
                  <div class="bg-slate-100 dark:bg-slate-950 p-2 sm:p-4 rounded-3xl border border-slate-200/80 dark:border-slate-800 shadow-inner">
                    <div class="bg-white rounded-2xl p-4 sm:p-8 shadow-sm border border-slate-200/60 max-w-[677px] mx-auto overflow-hidden">
                      <div v-html="wechatRenderedHtml" class="doocs-wechat-content select-text"></div>
                    </div>
                  </div>

                  <!-- Helpful Paste Guide Tip -->
                  <div class="p-3 bg-emerald-50 dark:bg-emerald-950/30 rounded-xl border border-emerald-200 dark:border-emerald-800 text-[11px] text-emerald-800 dark:text-emerald-300 leading-relaxed flex items-center gap-2">
                    <span class="text-base">💡</span>
                    <span>点击复制后，直接在微信公众号后台 (mp.weixin.qq.com) 粘贴 (Ctrl+V) 即可，已编译 100% 行内样式，标题徽章、引用块、居中插图与文末注脚完好保留！</span>
                  </div>
                </div>

              </div>

            </div>

            <!-- ============================================ -->
            <!-- SUB-VIEW 2: Official 900x383 Cover & 16:9 Quote Poster -->
            <!-- ============================================ -->
            <div v-if="wechatMode === 'visual'" class="space-y-6">
              
              <!-- 1. WeChat Official Cover 900x383 — Canvas preview -->
              <div v-if="wechatCover" class="space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                    <span>📰</span>
                    <span>微信官方头条大图封面 (900 × 383)</span>
                  </span>
                  <button
                    @click="downloadWechatCoverImage"
                    class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs rounded-xl font-bold transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>📸</span>
                    <span>{{ t.distribute.downloadCoverPng }}</span>
                  </button>
                </div>

                <!-- Canvas preview (pixel-identical to download) -->
                <div class="w-full aspect-[900/383] rounded-2xl overflow-hidden shadow-xl border border-slate-700/20 relative">
                  <img
                    v-if="wechatCoverPreviewImage"
                    :src="wechatCoverPreviewImage"
                    class="w-full h-full object-cover"
                    alt="微信封面预览"
                    draggable="false"
                  />
                  <div
                    v-else
                    class="absolute inset-0 flex items-center justify-center gap-3"
                    :class="selectedTheme === 'dark_gold' ? 'bg-gradient-to-r from-slate-900 to-indigo-950' : selectedTheme === 'indigo_purple' ? 'bg-gradient-to-r from-indigo-950 to-purple-900' : 'bg-slate-100'"
                  >
                    <div class="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                    <span class="text-xs text-white/50">渲染中…</span>
                  </div>
                </div>
              </div>

              <!-- 2. WeChat 16:9 Quote Card — Canvas preview -->
              <div v-if="wechatQuote" class="space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                    <span>💡</span>
                    <span>正文核心金句高光配图 (16:9 宽屏)</span>
                  </span>
                  <button
                    @click="downloadWechatQuoteImage"
                    class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-xl font-bold transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>📸</span>
                    <span>{{ t.distribute.downloadQuotePng }}</span>
                  </button>
                </div>

                <!-- Canvas preview (pixel-identical to download) -->
                <div class="w-full aspect-[16/9] max-w-2xl mx-auto rounded-2xl overflow-hidden shadow-xl border border-slate-700/20 relative">
                  <img
                    v-if="wechatQuotePreviewImage"
                    :src="wechatQuotePreviewImage"
                    class="w-full h-full object-cover"
                    alt="金句卡片预览"
                    draggable="false"
                  />
                  <div
                    v-else
                    class="absolute inset-0 flex items-center justify-center gap-3"
                    :class="selectedTheme === 'dark_gold' ? 'bg-gradient-to-br from-slate-900 to-indigo-950' : selectedTheme === 'indigo_purple' ? 'bg-gradient-to-br from-indigo-950 to-purple-900' : 'bg-slate-100'"
                  >
                    <div class="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                    <span class="text-xs text-white/50">渲染中…</span>
                  </div>
                </div>
              </div>

              <!-- 3. AI Image Generation Prompts -->
              <div v-if="wechatPrompts.length" class="space-y-3 pt-2">
                <h5 class="text-xs font-extrabold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                  <span>🤖</span>
                  <span>{{ t.distribute.imagePromptsTitle }}</span>
                </h5>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div
                    v-for="(p, pidx) in wechatPrompts"
                    :key="pidx"
                    class="p-4 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2 text-xs shadow-xs"
                  >
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-indigo-600 dark:text-indigo-400">{{ p.role }}</span>
                      <button
                        @click="copyText(`${p.prompt_zh}\n\n${p.prompt_en}`, `prompt_${pidx}`)"
                        class="text-xs font-semibold text-slate-500 hover:text-indigo-600 transition cursor-pointer"
                      >
                        {{ copiedPlatform === `prompt_${pidx}` ? '✓ 已复制' : t.distribute.copyPrompt }}
                      </button>
                    </div>
                    <p class="text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/60 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800">
                      <span class="font-semibold text-slate-500 mr-1">中文：</span>{{ p.prompt_zh }}
                    </p>
                    <p class="text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/60 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 font-mono text-[11px]">
                      <span class="font-semibold text-slate-500 mr-1">Prompt:</span>{{ p.prompt_en }}
                    </p>
                  </div>
                </div>
              </div>

            </div>

            <!-- ============================================ -->
            <!-- SUB-VIEW 3: Raw Markdown & Plaintext Mode    -->
            <!-- ============================================ -->
            <div v-if="wechatMode === 'text'" class="space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-slate-800 p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm">
                <div>
                  <h5 class="text-xs font-black text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                    微信公众号 Markdown 原始内容
                  </h5>
                  <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    展示未经编译的 Markdown 纯文本源码，支持快速取词或导入第三方编辑器。
                  </p>
                </div>
                <button
                  type="button"
                  @click="copyText(currentPlatformData?.content || '', 'wechat_raw')"
                  class="px-4 py-2.5 rounded-xl text-xs font-bold transition shadow-sm flex items-center gap-1.5 cursor-pointer active:scale-95 shrink-0 bg-slate-900 hover:bg-slate-800 text-white"
                >
                  <span>{{ copiedPlatform === 'wechat_raw' ? '✓' : '📋' }}</span>
                  <span>{{ copiedPlatform === 'wechat_raw' ? '✓ 纯文本已复制' : '复制 Markdown 原文' }}</span>
                </button>
              </div>

              <div class="bg-white dark:bg-slate-800 p-8 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm text-sm leading-relaxed whitespace-pre-wrap font-mono text-slate-800 dark:text-slate-200">
                {{ currentPlatformData?.content }}
              </div>
            </div>
          </div>

          <!-- ========================================== -->
          <!-- 3. TWITTER THREAD TAB                      -->
          <!-- ========================================== -->
          <div v-else-if="activeTab === 'twitter'" class="space-y-4">
            <div v-if="currentPlatformData?.thread && currentPlatformData.thread.length" class="space-y-3">
              <div
                v-for="(tweet, idx) in currentPlatformData?.thread || []"
                :key="idx"
                class="bg-white dark:bg-slate-800 p-5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm relative group"
              >
                <div class="flex items-center justify-between mb-2.5">
                  <span class="text-xs font-bold px-2.5 py-0.5 rounded-md bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-400 border border-sky-200 dark:border-sky-900">
                    {{ t.distribute.threadCard.replace('{index}', (idx + 1).toString()) }}
                  </span>
                  <button
                    @click="copyText(tweet, `tweet_${idx}`)"
                    class="text-xs font-bold text-slate-400 hover:text-sky-600 transition cursor-pointer"
                  >
                    {{ copiedPlatform === `tweet_${idx}` ? '✓ 已复制' : '复制本条' }}
                  </button>
                </div>
                <p class="text-sm leading-relaxed whitespace-pre-wrap text-slate-800 dark:text-slate-200">
                  {{ tweet }}
                </p>
              </div>
            </div>
            <div v-else class="bg-white dark:bg-slate-800 p-6 rounded-2xl border border-slate-200 dark:border-slate-700 text-sm whitespace-pre-wrap">
              {{ currentPlatformData?.content }}
            </div>
          </div>

          <!-- ========================================== -->
          <!-- 4. VIDEO SCRIPT TAB                        -->
          <!-- ========================================== -->
          <div v-else-if="activeTab === 'video'" class="space-y-4">
            <div v-if="currentPlatformData?.hook" class="p-5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-2xl text-amber-900 dark:text-amber-200">
              <p class="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-2">
                <span>⚡️</span>
                <span>{{ t.distribute.goldenHook }}</span>
              </p>
              <p class="text-sm font-medium whitespace-pre-wrap leading-relaxed">
                {{ currentPlatformData?.hook }}
              </p>
            </div>

            <div class="bg-white dark:bg-slate-800 p-6 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm text-sm leading-relaxed whitespace-pre-wrap font-sans text-slate-800 dark:text-slate-200">
              {{ currentPlatformData?.content }}
            </div>
          </div>

        </div>

        <div v-else class="py-16 text-center text-slate-400 text-sm">
          {{ t.distribute.empty }}
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 flex items-center justify-end">
        <button
          @click="closeModal"
          class="px-6 py-2.5 rounded-xl text-xs font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600 transition cursor-pointer"
        >
          {{ t.distribute.close }}
        </button>
      </div>

    </div>
  </div>
</template>