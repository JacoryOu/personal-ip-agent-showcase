<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
  >
    <div
      class="bg-white rounded-3xl max-w-3xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200/80 space-y-5 my-8 max-h-[90vh] flex flex-col relative overflow-hidden toast-enter"
    >
      <!-- Ambient Glow Decorator -->
      <div
        class="absolute -top-16 -right-16 w-56 h-56 bg-gradient-to-br from-indigo-200/40 via-purple-200/20 to-transparent rounded-full blur-3xl pointer-events-none"
      ></div>

      <!-- Celebration Toast Overlay / Banner -->
      <transition
        enter-active-class="transform transition ease-out duration-300"
        enter-from-class="translate-y-[-100%] opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition ease-in duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="celebrationMessage"
          class="absolute top-4 left-6 right-6 z-30 p-4 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 text-white shadow-xl flex items-center gap-3 border border-emerald-300/40 animate-pulse"
        >
          <span class="text-2xl shrink-0">🎉</span>
          <div class="flex-1 text-xs sm:text-sm font-bold">
            {{ celebrationMessage }}
          </div>
        </div>
      </transition>

      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-slate-100 pb-4 shrink-0 relative z-10">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center text-xl shadow-sm"
          >
            ✨
          </div>
          <div>
            <h3 class="text-lg font-black text-slate-900 flex items-center gap-2">
              <span>{{ t.ip_persona.extractModalTitle }}</span>
              <span
                class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200"
              >
                1-Click Reverse Extraction
              </span>
            </h3>
            <p class="text-xs text-slate-500 mt-0.5 max-w-xl">
              {{ t.ip_persona.extractModalSubtitle }}
            </p>
          </div>
        </div>
        <button
          type="button"
          @click="handleClose"
          :disabled="isExtracting || isAdopting"
          class="w-8 h-8 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center font-bold text-lg transition cursor-pointer disabled:opacity-40"
        >
          ✕
        </button>
      </div>

      <!-- State 1: Input Raw Text Form -->
      <div v-if="!extractedData" class="space-y-4 overflow-y-auto pr-1 flex-1 relative z-10">
        <!-- Quick Sample Presets -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              快速载入真实样例测试：
            </label>
            <button
              v-if="rawText.trim()"
              type="button"
              @click="rawText = ''"
              class="text-[11px] text-slate-400 hover:text-rose-500 transition cursor-pointer"
            >
              清空内容
            </button>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              type="button"
              v-for="(sample, idx) in samplePresets"
              :key="idx"
              @click="loadSample(sample.content)"
              class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 border border-slate-200/80 transition cursor-pointer active:scale-95"
            >
              {{ sample.label }}
            </button>
          </div>
        </div>

        <!-- Raw Textarea -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
            <span>过往旧文 / 随笔笔记 / 朋友圈文案 (Raw Text)</span>
            <span class="text-slate-400 font-mono text-[11px] font-normal">
              {{ rawText.length }} 字
            </span>
          </label>
          <textarea
            v-model="rawText"
            :placeholder="t.ip_persona.rawTextPlaceholder"
            rows="9"
            class="w-full bg-slate-50/80 border border-slate-200 rounded-2xl p-4 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none transition resize-none leading-relaxed"
          ></textarea>
        </div>

        <!-- Error Message Banner -->
        <div
          v-if="errorMessage"
          class="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2"
        >
          <span>⚠️</span>
          <span>{{ errorMessage }}</span>
        </div>
      </div>

      <!-- State 2: Extracted Preview & Editing -->
      <div v-else class="space-y-5 overflow-y-auto pr-1 flex-1 relative z-10">
        <!-- Preview Banner -->
        <div class="p-3.5 rounded-2xl bg-indigo-50/70 border border-indigo-100 flex items-center justify-between text-xs">
          <div class="flex items-center gap-2 text-indigo-900 font-bold">
            <span class="text-base">🪄</span>
            <span>已成功从文本中提取人设画像与故事！你可以在此微调，确认无误后一键激活。</span>
          </div>
          <button
            type="button"
            @click="extractedData = null"
            class="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 underline cursor-pointer"
          >
            ← 重新输入文本
          </button>
        </div>

        <!-- Extracted Persona Card -->
        <div class="bg-gradient-to-br from-indigo-50/40 via-purple-50/20 to-white border border-indigo-100 rounded-3xl p-5 shadow-xs space-y-4">
          <div class="flex items-center justify-between border-b border-indigo-100/60 pb-3">
            <h4 class="text-sm font-black text-slate-900 flex items-center gap-2">
              <span>🎭</span>
              <span>{{ t.ip_persona.previewPersonaTitle }}</span>
            </h4>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 border border-purple-200">
              IP Persona
            </span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <!-- Name -->
            <div>
              <label class="block text-xs font-bold text-slate-700 mb-1">
                {{ t.ip_persona.nameLabel }}
              </label>
              <input
                v-model="extractedPersona.name"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
              />
            </div>

            <!-- Salutation -->
            <div>
              <label class="block text-xs font-bold text-slate-700 mb-1">
                {{ t.ip_persona.salutationInputLabel }}
              </label>
              <input
                v-model="extractedPersona.reader_salutation"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
              />
            </div>

            <!-- Tone Style -->
            <div class="sm:col-span-2">
              <label class="block text-xs font-bold text-slate-700 mb-1">
                {{ t.ip_persona.toneLabel }}
              </label>
              <input
                v-model="extractedPersona.tone_style"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
              />
            </div>

            <!-- Target Audience -->
            <div class="sm:col-span-2">
              <label class="block text-xs font-bold text-slate-700 mb-1">
                {{ t.ip_persona.audienceLabel }}
              </label>
              <input
                v-model="extractedPersona.target_audience"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
              />
            </div>

            <!-- Origin Story -->
            <div class="sm:col-span-2">
              <label class="block text-xs font-bold text-slate-700 mb-1">
                {{ t.ip_persona.originStoryLabel }}
              </label>
              <textarea
                v-model="extractedPersona.origin_story"
                rows="4"
                class="w-full bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-800 leading-relaxed focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
              ></textarea>
            </div>
          </div>
        </div>

        <!-- Extracted Stories Section -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-black text-slate-900 flex items-center gap-2">
              <span>📖</span>
              <span>{{ t.ip_persona.previewStoriesTitle }}</span>
              <span class="text-xs text-slate-500 font-normal font-mono">
                ({{ extractedStories.length }})
              </span>
            </h4>
          </div>

          <div v-if="extractedStories.length > 0" class="space-y-3">
            <div
              v-for="(story, idx) in extractedStories"
              :key="idx"
              class="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-2xs space-y-2 text-left"
            >
              <div class="flex items-center justify-between gap-2">
                <input
                  v-model="story.title"
                  class="font-bold text-xs sm:text-sm text-slate-900 bg-transparent border-b border-transparent hover:border-slate-200 focus:border-indigo-400 outline-none flex-1"
                />
                <span
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0"
                >
                  {{ story.story_type || 'daily_life' }}
                </span>
              </div>
              <textarea
                v-model="story.story_content"
                rows="3"
                class="w-full text-xs text-slate-600 bg-slate-50/60 p-2.5 rounded-xl border border-slate-100 leading-relaxed outline-none focus:bg-white focus:border-indigo-300"
              ></textarea>
              <div class="flex items-center justify-between text-[11px] text-slate-400">
                <span v-if="story.occurred_at" class="font-mono">
                  📅 {{ story.occurred_at.split('T')[0] }}
                </span>
                <span v-else>📅 近期随笔</span>
                <div class="flex flex-wrap gap-1" v-if="story.tags && story.tags.length">
                  <span
                    v-for="tag in story.tags"
                    :key="tag"
                    class="text-[10px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded-md"
                  >
                    #{{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div
            v-else
            class="py-6 text-center text-xs text-slate-400 bg-slate-50/60 border border-dashed border-slate-200 rounded-2xl"
          >
            {{ t.ip_persona.noStoriesExtracted }}
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="border-t border-slate-100 pt-4 flex items-center justify-end gap-3 shrink-0 relative z-10">
        <button
          type="button"
          @click="handleClose"
          :disabled="isExtracting || isAdopting"
          class="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition cursor-pointer disabled:opacity-50"
        >
          {{ t.ip_persona.cancel }}
        </button>

        <!-- CTA 1: Start Extract -->
        <button
          v-if="!extractedData"
          type="button"
          @click="handleStartExtract"
          :disabled="!rawText.trim() || isExtracting"
          class="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md shadow-indigo-500/20 transition active:scale-95 cursor-pointer disabled:opacity-50 flex items-center gap-2"
        >
          <span v-if="isExtracting" class="animate-spin">⏳</span>
          <span v-else>✨</span>
          <span>{{ isExtracting ? t.ip_persona.extractingBtn : t.ip_persona.startExtractBtn }}</span>
        </button>

        <!-- CTA 2: Adopt & Activate -->
        <button
          v-else
          type="button"
          @click="handleAdoptAndActivate"
          :disabled="isAdopting || !extractedPersona.name"
          class="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 hover:from-emerald-700 hover:to-indigo-700 shadow-md shadow-emerald-500/25 transition active:scale-95 cursor-pointer disabled:opacity-50 flex items-center gap-2"
        >
          <span v-if="isAdopting" class="animate-spin">⏳</span>
          <span v-else>🎉</span>
          <span>{{ isAdopting ? t.ip_persona.adoptingBtn : t.ip_persona.adoptAndActivateBtn }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useI18n } from '../i18n'
import {
  extractPersonaFromText,
  fetchPersonas,
  createPersona,
  activatePersona,
  createStory,
  type IPPersona,
  type EpisodicStoryItem,
} from '../services/api'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'adopted', persona: IPPersona): void
}>()

const { t } = useI18n()

const rawText = ref('')
const isExtracting = ref(false)
const isAdopting = ref(false)
const errorMessage = ref('')
const celebrationMessage = ref('')
const extractedData = ref<any | null>(null)

const extractedPersona = reactive<Partial<IPPersona>>({
  name: '',
  target_audience: '',
  tone_style: '',
  reader_salutation: '',
  origin_story: '',
  is_active: true,
})

const extractedStories = ref<Partial<EpisodicStoryItem>[]>([])

const samplePresets = computed(() => [
  {
    label: t.value.ip_persona?.sampleButton2 || '🍵 健康养生实战',
    content: `我做新会陈皮茶饮已经有八个年头了。很多刚加我微信的姐妹都会问我：阿姨，我湿气重常年头晕乏力，到底该怎么调？
其实两年前我也走过大弯路，以为只要天天喝重苦的凉茶就能排毒，结果脾胃越来越虚弱，一到换季就胃痛胃胀。
直到后来我向我们岭南老中医请教，才明白湿气的根源在“脾胃虚弱，运化失常”。
所以我总是告诉宝子们：千万别盲目断食或者喝大寒的生冷饮品。用五年以上的温润新会老陈皮配上伏苓和炒白术，慢火细煨，顺应时令，脾阳起来了，水湿自然就散了。
这些年我带过不下两千位体制虚寒的宝妈与职场女性，看到大家气色变红润，是我最有成就感的事。`,
  },
  {
    label: t.value.ip_persona?.sampleButton3 || '🚀 自由职业与创业踩坑',
    content: `从大厂裸辞做个人IP的第一年，我几乎每天都在焦虑中失眠。
当时觉得自己懂技术、懂架构，做点数字化咨询还不是信手拈来？结果前三个月连一个付费客户都没谈成，银行卡余额掉到只剩两千块。
那一刻我才彻底顿悟：在企业里，是平台的光环在给你兜底；而走出来单打独斗，客户买的是你真实解决问题的信任与交付成果。
后来我转变思路，不再高高在上聊宏大叙事，而是每天在朋友圈记录我解决的每一个具体Bug、每一个小商家的自动化落地方案。
半年后，咨询订单排到了三个月后。我想对所有想开启副业与自由职业的朋友说：放下身段，从离金钱最近的一桩小交付做起。`,
  },
  {
    label: t.value.ip_persona?.sampleButton1 || '🌱 认知反思与个人成长',
    content: `最近重读芒格的书，我越来越感受到“慢即是快”的重量。
年轻时总想走捷径，看到什么风口都想扑上去，结果交了一大笔学费。现在步入三十五岁，我学会了把时间花在可复利的认知资产上。
每天清晨写作一小时，梳理当天的思考指纹，向内审视自己的偏见与傲慢。
希望我的文字能陪伴每一位在路上探索自我边界的终身学习者，在这个充满算法噪音的时代，守住我们内心的清澈与笃定。`,
  },
])

function loadSample(text: string) {
  rawText.value = text
  errorMessage.value = ''
}

function handleClose() {
  if (isExtracting.value || isAdopting.value) return
  emit('close')
}

// Reset state when modal is opened
watch(
  () => props.show,
  (val) => {
    if (val) {
      errorMessage.value = ''
      celebrationMessage.value = ''
      if (!rawText.value) {
        // default empty or keep previous
      }
    }
  }
)

async function handleStartExtract() {
  const text = rawText.value.trim()
  if (!text || isExtracting.value) return

  isExtracting.value = true
  errorMessage.value = ''

  try {
    const res = await extractPersonaFromText(text, false)
    extractedData.value = res

    // Normalize persona fields
    const p = res.persona || (res as any)
    extractedPersona.name = p.name || '萃取IP分身'
    extractedPersona.reader_salutation = p.reader_salutation || '朋友们'
    extractedPersona.tone_style = p.tone_style || '真诚温暖、富有实战经验'
    extractedPersona.target_audience = p.target_audience || '追求个人成长与品质生活的读者群体'
    extractedPersona.origin_story = p.origin_story || text.slice(0, 300)
    extractedPersona.is_active = true

    // Normalize stories
    if (res.stories && Array.isArray(res.stories)) {
      extractedStories.value = res.stories
    } else {
      extractedStories.value = []
    }
  } catch (err: any) {
    console.error('Extract persona failed:', err)
    errorMessage.value = err.message || '萃取失败，请检查网络或配置'
  } finally {
    isExtracting.value = false
  }
}

async function handleAdoptAndActivate() {
  if (isAdopting.value || !extractedPersona.name?.trim()) return

  isAdopting.value = true
  errorMessage.value = ''

  try {
    let savedPersona: IPPersona

    // If already saved with an id from server
    if (extractedData.value?.persona?.id && extractedData.value?.saved) {
      savedPersona = extractedData.value.persona
    } else {
      // Create new persona
      savedPersona = await createPersona({
        name: extractedPersona.name.trim(),
        target_audience: extractedPersona.target_audience?.trim() || '',
        tone_style: extractedPersona.tone_style?.trim() || '',
        reader_salutation: extractedPersona.reader_salutation?.trim() || '',
        origin_story: extractedPersona.origin_story?.trim() || '',
        is_active: true,
      })
    }

    // Ensure single active persona
    try {
      const existing = await fetchPersonas()
      for (const p of existing) {
        if (p.is_active && p.id !== savedPersona.id) {
          await activatePersona(p.id, false)
        }
      }
      await activatePersona(savedPersona.id, true)
    } catch (actErr) {
      console.warn('Deactivating previous active personas error:', actErr)
    }

    // Save extracted stories if not already saved
    if (extractedStories.value && extractedStories.value.length > 0) {
      for (const st of extractedStories.value) {
        if (!st.id && st.story_content?.trim()) {
          try {
            await createStory({
              title: st.title || '人生切片',
              story_type: st.story_type || 'daily_life',
              occurred_at: st.occurred_at || new Date().toISOString(),
              story_content: st.story_content.trim(),
              tags: st.tags || ['萃取故事'],
            })
          } catch (stErr) {
            console.warn('Failed to save story chunk:', stErr)
          }
        }
      }
    }

    // Show celebration toast
    celebrationMessage.value = `🎉 恭喜！专属 IP 人设「${savedPersona.name}」已采纳并成功激活！`

    emit('adopted', savedPersona)

    // Close after short celebration
    setTimeout(() => {
      celebrationMessage.value = ''
      extractedData.value = null
      rawText.value = ''
      emit('close')
    }, 1600)
  } catch (err: any) {
    console.error('Adopt persona failed:', err)
    errorMessage.value = err.message || '采纳保存失败，请稍后重试'
  } finally {
    isAdopting.value = false
  }
}
</script>
