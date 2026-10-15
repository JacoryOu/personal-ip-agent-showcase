<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
  >
    <div class="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-5 my-8 max-h-[90vh] flex flex-col toast-enter">
      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-slate-100 pb-4 shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl border border-amber-200">
            ⚡
          </div>
          <div>
            <h3 class="text-lg font-black text-slate-900 flex items-center gap-2">
              <span>{{ t.blueprint.deconstructModalTitle || '爆款对标一键拆骨提炼' }}</span>
              <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
                骨架萃取 (Bone Extraction)
              </span>
            </h3>
            <p class="text-xs text-slate-500 mt-0.5">
              {{ t.blueprint.deconstructModalSubtitle || '将外部爆款长文拆解为结构骨架与情绪弧线，保持认知画像独立零污染。' }}
            </p>
          </div>
        </div>
        <button
          type="button"
          @click="closeModal"
          class="w-8 h-8 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center font-bold text-lg transition"
        >
          ✕
        </button>
      </div>

      <!-- State 1: Input Form -->
      <div v-if="!result" class="space-y-4 overflow-y-auto pr-1 flex-1">
        <!-- Input Mode Switcher -->
        <div class="flex items-center gap-2 text-xs font-bold bg-slate-100 p-1 rounded-xl w-fit">
          <button
            type="button"
            @click="inputMode = 'text'"
            class="px-3 py-1.5 rounded-lg transition"
            :class="inputMode === 'text' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
          >
            📝 粘贴爆款正文
          </button>
          <button
            type="button"
            @click="inputMode = 'url'"
            class="px-3 py-1.5 rounded-lg transition"
            :class="inputMode === 'url' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
          >
            🔗 微信/知乎/网页链接
          </button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              爆款文章标题 / 选题标记 (可选)
            </label>
            <input
              v-model="benchmarkTitle"
              type="text"
              placeholder="例如：为什么顶级操盘手都不看转化率..."
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 focus:bg-white focus:ring-2 focus:ring-amber-500 focus:outline-none"
            />
          </div>

          <div v-if="inputMode === 'url'">
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              文章完整 URL <span class="text-red-500">*</span>
            </label>
            <input
              v-model="benchmarkUrl"
              type="url"
              placeholder="https://mp.weixin.qq.com/s/... 或 https://zhuanlan.zhihu.com/p/..."
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 focus:bg-white focus:ring-2 focus:ring-amber-500 focus:outline-none font-mono"
            />
          </div>

          <div v-else>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              爆款正文内容 <span class="text-red-500">*</span>
            </label>
            <textarea
              v-model="benchmarkContent"
              rows="9"
              placeholder="直接将微信公众号、知乎专栏或小红书长文正文粘贴在此处。系统将自动剥离具体事例与血肉，提炼底层行文骨架..."
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 focus:bg-white focus:ring-2 focus:ring-amber-500 focus:outline-none leading-relaxed"
            ></textarea>
          </div>
        </div>

        <!-- Tip Box -->
        <div class="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-3.5 flex items-start gap-2.5 text-xs text-amber-900 leading-relaxed">
          <span class="text-base">💡</span>
          <div>
            <strong>拆骨机制保障：</strong> 拆解爆款绝不污染您独有的 Thinking DNA。系统仅沉淀行文节奏、破题技巧与情绪张力，真正实现「借他人之骨，长自己之肉」。
          </div>
        </div>

        <!-- Error Alert -->
        <div v-if="errorMessage" class="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
          ⚠️ {{ errorMessage }}
        </div>
      </div>

      <!-- State 2: Result Display -->
      <div v-else class="space-y-4 overflow-y-auto pr-1 flex-1">
        <!-- Blueprint Overview Card -->
        <div class="bg-gradient-to-br from-amber-50/80 via-orange-50/40 to-white border border-amber-200 rounded-2xl p-5 space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-black text-amber-900 flex items-center gap-1.5">
              <span>🦴</span>
              <span>已提炼爆款骨架 (Blueprint)</span>
            </span>
            <span class="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full">
              已沉淀入库
            </span>
          </div>

          <h4 class="text-base font-black text-slate-900">
            {{ result.blueprint.title }}
          </h4>

          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
            <div class="bg-white/80 border border-amber-100 p-2.5 rounded-xl">
              <div class="text-[10px] font-bold text-slate-400 uppercase">破题抓手 (Hook)</div>
              <div class="text-xs font-bold text-slate-800 mt-0.5 line-clamp-2">{{ result.blueprint.hook_style }}</div>
            </div>
            <div class="bg-white/80 border border-amber-100 p-2.5 rounded-xl">
              <div class="text-[10px] font-bold text-slate-400 uppercase">情绪弧线 (Arc)</div>
              <div class="text-xs font-bold text-slate-800 mt-0.5 line-clamp-2">{{ result.blueprint.emotional_arc }}</div>
            </div>
            <div class="bg-white/80 border border-amber-100 p-2.5 rounded-xl">
              <div class="text-[10px] font-bold text-slate-400 uppercase">行文节奏 (Pacing)</div>
              <div class="text-xs font-bold text-slate-800 mt-0.5 line-clamp-2">{{ result.blueprint.pacing }}</div>
            </div>
          </div>

          <!-- Structural Stages List -->
          <div class="pt-2 border-t border-amber-100">
            <div class="text-[11px] font-bold text-slate-700 mb-1.5">4 步结构演进阶段：</div>
            <div class="space-y-1.5">
              <div
                v-for="(stage, idx) in result.blueprint.structural_stages"
                :key="idx"
                class="flex items-center gap-2 text-xs text-slate-700 bg-white/70 px-3 py-1.5 rounded-lg border border-amber-100/60"
              >
                <span class="w-5 h-5 rounded-full bg-amber-200 text-amber-900 font-black text-[10px] flex items-center justify-center shrink-0">
                  {{ idx + 1 }}
                </span>
                <span class="font-medium">{{ stage }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Clash Points Section -->
        <div v-if="result.clash_points && result.clash_points.length > 0" class="space-y-2.5">
          <div class="text-xs font-bold text-slate-800 flex items-center justify-between">
            <span>⚔️ 审议爆款论断 (可选择注入你的反共识立场)：</span>
            <span class="text-[10px] text-slate-400">{{ result.clash_points.length }} 处观点</span>
          </div>

          <div
            v-for="(cp, idx) in result.clash_points"
            :key="idx"
            class="border border-slate-200 rounded-xl p-3 space-y-2 bg-slate-50/50"
          >
            <div class="text-xs text-slate-800">
              <strong class="text-amber-800 font-bold">爆款论断：</strong>“{{ cp.claim }}”
            </div>
            <div class="text-[11px] text-slate-500">
              <strong>批判指引：</strong>{{ cp.suggested_critique_angle }}
            </div>
            <input
              v-model="rebuttals[idx]"
              type="text"
              placeholder="输入你的反驳主张或独特观察 (可选)..."
              class="w-full text-xs bg-white border border-slate-300 rounded-lg p-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="border-t border-slate-100 pt-4 flex items-center justify-between shrink-0">
        <button
          v-if="result"
          type="button"
          @click="resetForm"
          class="text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          ← 拆解另一篇文章
        </button>
        <span v-else></span>

        <div class="flex items-center gap-3">
          <button
            type="button"
            @click="closeModal"
            class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
          >
            关闭
          </button>

          <!-- Submit Button in State 1 -->
          <button
            v-if="!result"
            type="button"
            :disabled="isSubmitting || (inputMode === 'url' ? !benchmarkUrl.trim() : !benchmarkContent.trim())"
            @click="handleDeconstruct"
            class="px-5 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl disabled:opacity-50 transition shadow-sm flex items-center gap-1.5 active:scale-95"
          >
            <svg v-if="isSubmitting" class="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>{{ isSubmitting ? '正在一键拆骨提炼...' : '⚡ 一键拆骨提炼' }}</span>
          </button>

          <!-- Primary Action in State 2: Create in Workbench -->
          <button
            v-else
            type="button"
            @click="handleCreateWithBlueprint"
            class="px-5 py-2 text-xs font-bold text-white bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 rounded-xl shadow-md shadow-amber-500/20 active:scale-95 transition flex items-center gap-1.5"
          >
            <span>🦴</span>
            <span>立即以此骨架去工坊创作</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '../i18n'
import {
  deconstructBenchmark,
  recordDialogueClash,
  type BenchmarkBlueprint,
  type BenchmarkDeconstructionResult,
} from '../services/api'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'close'): void
  (e: 'create-with-blueprint', payload: { blueprint: BenchmarkBlueprint }): void
  (e: 'blueprint-saved', blueprint: BenchmarkBlueprint): void
}>()

const inputMode = ref<'text' | 'url'>('text')
const benchmarkTitle = ref('')
const benchmarkUrl = ref('')
const benchmarkContent = ref('')
const isSubmitting = ref(false)
const errorMessage = ref('')
const result = ref<BenchmarkDeconstructionResult | null>(null)
const rebuttals = ref<Record<number, string>>({})

function closeModal() {
  emit('update:show', false)
  emit('close')
}

function resetForm() {
  result.value = null
  benchmarkTitle.value = ''
  benchmarkUrl.value = ''
  benchmarkContent.value = ''
  errorMessage.value = ''
  rebuttals.value = {}
}

async function handleDeconstruct() {
  errorMessage.value = ''
  isSubmitting.value = true

  try {
    const payload = {
      content: inputMode.value === 'text' ? benchmarkContent.value.trim() : undefined,
      url: inputMode.value === 'url' ? benchmarkUrl.value.trim() : undefined,
      title: benchmarkTitle.value.trim() || undefined,
    }

    const res = await deconstructBenchmark(payload)
    result.value = res
    emit('blueprint-saved', res.blueprint)
  } catch (err: any) {
    errorMessage.value = err.message || '拆骨提炼失败，请检查文章格式或后端服务。'
  } finally {
    isSubmitting.value = false
  }
}

async function handleCreateWithBlueprint() {
  if (!result.value?.blueprint) return

  // If user entered rebuttals, capture them asynchronously
  const clashMessages: Array<{ role: string; content: string }> = []
  if (result.value.clash_points) {
    result.value.clash_points.forEach((cp, idx) => {
      const reb = rebuttals.value[idx]?.trim()
      if (reb) {
        clashMessages.push({ role: 'assistant', content: `原论点: ${cp.claim}` })
        clashMessages.push({ role: 'user', content: reb })
      }
    })
  }

  if (clashMessages.length > 0) {
    try {
      await recordDialogueClash({
        messages: clashMessages,
        debate_topic: result.value.blueprint.title,
      })
    } catch {
      // non-blocking
    }
  }

  emit('create-with-blueprint', { blueprint: result.value.blueprint })
  closeModal()
}
</script>
