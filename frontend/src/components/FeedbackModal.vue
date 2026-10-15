<template>
  <div
    class="fixed inset-0 z-50 glass-card-dark flex items-center justify-center p-3 sm:p-5 md:p-6"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-3xl max-w-4xl w-full max-h-[92vh] shadow-2xl flex flex-col overflow-hidden toast-enter border border-slate-200/80">
      <!-- Modal Gradient Header (Requirement 3: Sleek Gradient Header) -->
      <div class="px-6 py-5 border-b border-slate-800/20 bg-gradient-to-r from-slate-950 via-indigo-950 to-purple-950 text-white relative overflow-hidden flex items-center justify-between">
        <!-- Subtle background glow -->
        <div class="absolute -right-8 -top-8 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none"></div>

        <div class="flex items-center gap-3.5 relative z-10">
          <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center text-white text-xl shadow-lg ring-2 ring-white/10">
            📊
          </div>
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <h2 class="text-base sm:text-lg font-black tracking-tight text-white">
                {{ t.feedback.drawerTitle }}
              </h2>
              <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-white/10 text-indigo-200 border border-white/15 max-w-[240px] truncate backdrop-blur-xs">
                {{ draftTopic || '当前草稿' }}
              </span>
            </div>
            <p class="text-xs text-slate-300/90 mt-0.5">
              {{ t.feedback.drawerSubtitle }}
            </p>
          </div>
        </div>

        <button
          type="button"
          @click="emit('close')"
          class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition cursor-pointer relative z-10"
        >
          ✕
        </button>
      </div>

      <!-- Navigation Tabs (Requirement 3: Smooth Tab Transition) -->
      <div class="px-6 py-3 bg-slate-50 border-b border-slate-200/80 flex items-center justify-between gap-3">
        <div class="bg-slate-200/70 p-1 rounded-2xl flex items-center gap-1 border border-slate-300/40">
          <button
            type="button"
            @click="activeTab = 'input'"
            class="px-4 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5"
            :class="activeTab === 'input' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'"
          >
            <span>⚡</span>
            <span>{{ t.feedback.tabExtract }}</span>
          </button>

          <button
            type="button"
            @click="switchTab('records')"
            class="px-4 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5"
            :class="activeTab === 'records' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'"
          >
            <span>📜</span>
            <span>{{ t.feedback.tabRecords }}</span>
            <span
              class="px-1.5 py-0.2 rounded-full text-[10px] font-mono"
              :class="activeTab === 'records' ? 'bg-indigo-100 text-indigo-800' : 'bg-slate-300 text-slate-700'"
            >
              {{ feedbackRecords.length }}
            </span>
          </button>
        </div>

        <div v-if="latestExtractResult" class="flex items-center gap-1.5">
          <span class="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200 shadow-2xs">
            <span>✓</span>
            <span>已成功进化 {{ latestExtractResult.boosted_traits.length }} 项思维 DNA</span>
          </span>
        </div>
      </div>

      <!-- Toast Feedback Message -->
      <div
        v-if="toastMsg"
        class="mx-6 mt-4 p-3.5 rounded-2xl border text-xs font-bold flex items-center justify-between shadow-2xs toast-enter"
        :class="toastType === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'"
      >
        <div class="flex items-center gap-2">
          <span>{{ toastType === 'error' ? '⚠️' : '🎉' }}</span>
          <span>{{ toastMsg }}</span>
        </div>
        <button @click="toastMsg = ''" class="hover:opacity-75 cursor-pointer font-bold">✕</button>
      </div>

      <!-- Main Scrollable Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- ======================================================== -->
        <!-- TAB 1: INPUT & EXTRACTION -->
        <!-- ======================================================== -->
        <div v-if="activeTab === 'input'" class="space-y-6">
          <!-- Reader Comments Textarea -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-black text-slate-800 uppercase tracking-wide">
                {{ t.feedback.commentsLabel }} <span class="text-rose-500">*</span>
              </label>

              <!-- Quick Demo Templates for delight -->
              <div class="flex items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  @click="applyTemplate('resonance')"
                  class="text-indigo-600 hover:text-indigo-800 font-semibold bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded-lg border border-indigo-200/60 cursor-pointer transition"
                >
                  + 高共鸣好评模版
                </button>
                <button
                  type="button"
                  @click="applyTemplate('critique')"
                  class="text-amber-700 hover:text-amber-900 font-semibold bg-amber-50 hover:bg-amber-100 px-2 py-0.5 rounded-lg border border-amber-200/60 cursor-pointer transition"
                >
                  + 深度反思模版
                </button>
              </div>
            </div>

            <textarea
              v-model="commentsInput"
              rows="5"
              :placeholder="t.feedback.commentsPlaceholder"
              class="w-full px-4 py-3 text-xs text-slate-800 leading-relaxed border border-slate-300 rounded-2xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition resize-y font-sans shadow-2xs"
            ></textarea>
          </div>

          <!-- Engagement Metrics Inputs (Collapsible/Inline) -->
          <div class="p-4 rounded-2xl bg-slate-50/80 border border-slate-200 space-y-3 shadow-2xs">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>📈</span>
                <span>{{ t.feedback.metricsTitle }}</span>
              </span>
              <span class="text-[11px] text-slate-400">结合互动热度更精准计算置信度权重增量</span>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <label class="block text-slate-500 text-[11px] font-medium mb-1">{{ t.feedback.likesLabel }}</label>
                <input
                  v-model.number="metrics.likes"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none text-slate-800 font-mono"
                />
              </div>

              <div>
                <label class="block text-slate-500 text-[11px] font-medium mb-1">{{ t.feedback.readsLabel }}</label>
                <input
                  v-model.number="metrics.reads"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none text-slate-800 font-mono"
                />
              </div>

              <div>
                <label class="block text-slate-500 text-[11px] font-medium mb-1">{{ t.feedback.commentsCountLabel }}</label>
                <input
                  v-model.number="metrics.comments"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none text-slate-800 font-mono"
                />
              </div>

              <div>
                <label class="block text-slate-500 text-[11px] font-medium mb-1">{{ t.feedback.sharesLabel }}</label>
                <input
                  v-model.number="metrics.shares"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none text-slate-800 font-mono"
                />
              </div>
            </div>
          </div>

          <!-- Live DNA Boost Animation / Badge Preview (Requirement 3: Live DNA Boost Animation) -->
          <div
            v-if="commentsInput.trim().length > 0 && !latestExtractResult"
            class="p-4 rounded-2xl bg-gradient-to-br from-indigo-50/70 via-purple-50/50 to-pink-50/30 border border-indigo-200/80 shadow-2xs space-y-2.5 animate-in fade-in duration-200"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse"></span>
                <span class="text-xs font-black text-indigo-950 uppercase tracking-wide">
                  ⚡ 预期认知跃迁与 DNA 演化预测 (Live DNA Boost Preview)
                </span>
              </div>
              <span class="text-[10px] font-extrabold text-indigo-700 bg-white px-2 py-0.5 rounded-full border border-indigo-200 shadow-2xs">
                预估置信度增幅: +0.2 ~ +0.5x
              </span>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
              <div class="bg-white/80 p-2.5 rounded-xl border border-indigo-100 text-xs space-y-0.5">
                <span class="text-[10px] font-bold text-indigo-600">🎯 核心论点</span>
                <p class="text-[11px] text-slate-700 font-medium">读者深度认同的高光观点将强化为置顶先验</p>
              </div>
              <div class="bg-white/80 p-2.5 rounded-xl border border-purple-100 text-xs space-y-0.5">
                <span class="text-[10px] font-bold text-purple-600">📚 词汇指纹</span>
                <p class="text-[11px] text-slate-700 font-medium">高频热议金句将沉淀为专属词汇库权重</p>
              </div>
              <div class="bg-white/80 p-2.5 rounded-xl border border-pink-100 text-xs space-y-0.5">
                <span class="text-[10px] font-bold text-pink-600">💡 选题灵感</span>
                <p class="text-[11px] text-slate-700 font-medium">争议点与催更方向将自动沉淀素材库 Inbox</p>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex flex-wrap items-center justify-end gap-3 pt-2">
            <button
              type="button"
              @click="handleSaveOnly"
              :disabled="!commentsInput.trim() || isSaving || isExtracting"
              class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition cursor-pointer disabled:opacity-50 active:scale-95"
            >
              <span>{{ isSaving ? t.feedback.saving : t.feedback.saveOnlyBtn }}</span>
            </button>

            <button
              type="button"
              @click="handleExtractAndEvolve"
              :disabled="!commentsInput.trim() || isExtracting || isSaving"
              class="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:opacity-95 shadow-md shadow-indigo-500/20 active:scale-95 transition cursor-pointer disabled:opacity-50"
            >
              <span v-if="isExtracting" class="animate-spin">⚡</span>
              <span>{{ isExtracting ? t.feedback.extracting : t.feedback.submitAndExtractBtn }}</span>
            </button>
          </div>

          <!-- Real-time Extracted Insights Showcase (Requirement 3: Live DNA Boost Animation/Badge Preview) -->
          <div v-if="latestExtractResult" class="space-y-4 pt-4 border-t border-slate-100 animate-in fade-in slide-in-from-top-4 duration-300">
            <!-- Evolution Summary Pill -->
            <div class="p-4 rounded-2xl bg-gradient-to-r from-purple-50/80 to-indigo-50/80 border border-purple-200 text-xs flex items-start gap-3 shadow-2xs">
              <span class="text-xl">🧬</span>
              <div class="space-y-1">
                <span class="font-black text-purple-950 uppercase tracking-wide">{{ t.feedback.evolutionSummaryTitle }}：</span>
                <p class="text-purple-900 leading-relaxed font-medium">{{ latestExtractResult.evolution_summary }}</p>
              </div>
            </div>

            <!-- Boosted Thinking DNA Traits Showcase -->
            <div v-if="latestExtractResult.boosted_traits.length > 0" class="space-y-2.5">
              <h3 class="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase tracking-wide">
                <span>🧬</span>
                <span>{{ t.feedback.dnaBoostTitle }}</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] bg-indigo-100 text-indigo-800 font-extrabold">
                  +{{ latestExtractResult.boosted_traits.length }} 项完成置信度跃迁
                </span>
              </h3>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div
                  v-for="trait in latestExtractResult.boosted_traits"
                  :key="trait.id"
                  class="p-4 rounded-2xl bg-white border-2 border-indigo-200 shadow-xs flex flex-col justify-between space-y-3 hover:border-indigo-400 transition"
                >
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-1.5 flex-wrap">
                      <span class="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {{ formatDimension(trait.dimension) }}
                      </span>
                      <span class="inline-flex items-center gap-1 text-[11px] font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-200 shadow-2xs font-mono">
                        <span>🔥 {{ trait.old_confidence }} → {{ trait.new_confidence }}x</span>
                        <span class="text-[9px] text-emerald-600">(+{{ trait.boost_amount }})</span>
                      </span>
                    </div>

                    <p class="text-xs font-bold text-slate-800 leading-snug">
                      {{ trait.statement }}
                    </p>
                  </div>

                  <p v-if="trait.reason" class="text-[10px] text-slate-500 border-t border-slate-100 pt-2 italic">
                    {{ trait.reason }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Resonant Ideas List -->
            <div v-if="latestExtractResult.resonant_ideas.length > 0" class="space-y-2">
              <h3 class="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase tracking-wide">
                <span>🔥</span>
                <span>{{ t.feedback.resonantTitle }}</span>
              </h3>
              <div class="space-y-1.5">
                <div
                  v-for="(idea, idx) in latestExtractResult.resonant_ideas"
                  :key="idx"
                  class="p-3 rounded-2xl bg-amber-50/70 border border-amber-200 text-xs text-amber-950 font-medium flex items-start gap-2.5 shadow-2xs"
                >
                  <span class="text-amber-600 font-black">#{{ idx + 1 }}</span>
                  <span class="leading-relaxed">{{ idea }}</span>
                </div>
              </div>
            </div>

            <!-- Controversy Points -->
            <div v-if="latestExtractResult.controversy_points.length > 0" class="space-y-2">
              <h3 class="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase tracking-wide">
                <span>⚡</span>
                <span>{{ t.feedback.controversyTitle }}</span>
              </h3>
              <div class="space-y-1.5">
                <div
                  v-for="(cp, idx) in latestExtractResult.controversy_points"
                  :key="idx"
                  class="p-3 rounded-2xl bg-rose-50/70 border border-rose-200 text-xs text-rose-950 font-medium flex items-start gap-2.5 shadow-2xs"
                >
                  <span class="text-rose-600 font-black text-sm">!</span>
                  <span class="leading-relaxed">{{ cp }}</span>
                </div>
              </div>
            </div>

            <!-- Auto-Saved Personal Notes in MaterialVault -->
            <div v-if="latestExtractResult.created_materials.length > 0" class="space-y-2">
              <div class="flex items-center justify-between">
                <h3 class="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase tracking-wide">
                  <span>💡</span>
                  <span>{{ t.feedback.inspirationsTitle }}</span>
                </h3>
                <span class="text-[10px] text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full font-bold border border-indigo-200">
                  已存入素材库 · 随时二创
                </span>
              </div>

              <div class="space-y-2">
                <div
                  v-for="mat in latestExtractResult.created_materials"
                  :key="mat.id"
                  class="p-3.5 rounded-2xl bg-purple-50/50 border border-purple-200 text-xs space-y-1.5 shadow-2xs"
                >
                  <div class="flex items-center justify-between">
                    <span class="font-bold text-purple-950">{{ mat.title }}</span>
                    <span class="text-[10px] text-purple-700 font-semibold bg-white px-2 py-0.5 rounded-md border border-purple-100">Inbox 灵感</span>
                  </div>
                  <p class="text-slate-600 line-clamp-2 leading-relaxed">
                    {{ mat.cleaned_content }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- TAB 2: HISTORICAL FEEDBACK RECORDS -->
        <!-- ======================================================== -->
        <div v-else-if="activeTab === 'records'" class="space-y-4">
          <div v-if="isLoadingRecords" class="py-16 text-center text-slate-400 text-xs">
            <span class="animate-spin text-2xl block mb-2">⏳</span>
            <span class="font-medium">加载反馈归档记录中...</span>
          </div>

          <div
            v-else-if="feedbackRecords.length === 0"
            class="py-16 text-center border-2 border-dashed border-slate-200 rounded-3xl p-6"
          >
            <span class="text-4xl block mb-3">📬</span>
            <p class="text-xs font-bold text-slate-600">
              {{ t.feedback.emptyRecords }}
            </p>
            <button
              type="button"
              @click="activeTab = 'input'"
              class="mt-4 px-5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition cursor-pointer shadow-xs active:scale-95"
            >
              立即录入读者评论
            </button>
          </div>

          <div v-else class="space-y-3.5">
            <div
              v-for="rec in feedbackRecords"
              :key="rec.id"
              class="p-5 rounded-3xl border border-slate-200/90 bg-white shadow-xs space-y-3 hover:border-slate-300 transition"
            >
              <div class="flex items-center justify-between text-xs flex-wrap gap-2">
                <span class="text-slate-400 font-mono text-[11px] bg-slate-50 px-2.5 py-0.5 rounded-md border border-slate-100">
                  🕒 {{ formatTime(rec.created_at) }}
                </span>

                <div class="flex items-center gap-2 flex-wrap">
                  <span v-if="rec.metrics?.likes" class="text-slate-600 font-semibold text-[11px] bg-slate-50 px-2 py-0.5 rounded-md border border-slate-100">
                    👍 {{ rec.metrics.likes }}
                  </span>
                  <span v-if="rec.metrics?.reads" class="text-slate-600 font-semibold text-[11px] bg-slate-50 px-2 py-0.5 rounded-md border border-slate-100">
                    👁️ {{ rec.metrics.reads }}
                  </span>
                  <span v-if="rec.metrics?.shares" class="text-slate-600 font-semibold text-[11px] bg-slate-50 px-2 py-0.5 rounded-md border border-slate-100">
                    ↗️ {{ rec.metrics.shares }}
                  </span>
                  <span
                    v-if="rec.boosted_dna_traits?.length"
                    class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200 shadow-2xs"
                  >
                    ⚡ 已强化 {{ rec.boosted_dna_traits.length }} 项DNA
                  </span>
                </div>
              </div>

              <!-- Raw Comments Preview -->
              <p class="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50/80 p-3.5 rounded-2xl border border-slate-100 font-sans">
                {{ rec.comments_text }}
              </p>

              <!-- Extracted Summary if any -->
              <div v-if="rec.extracted_insights?.evolution_summary" class="text-[11px] text-purple-950 bg-purple-50/60 p-3 rounded-xl border border-purple-200/80 leading-relaxed">
                🧬 <span class="font-bold">演化洞察：</span>{{ rec.extracted_insights.evolution_summary }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Bar -->
      <div class="px-6 py-3.5 border-t border-slate-200 flex items-center justify-between bg-slate-50 text-xs">
        <span class="text-slate-400 text-[11px] flex items-center gap-1">
          <span>🌱</span>
          <span>读者共鸣驱动 Thinking DNA 权重迭代，完成认知飞轮闭环</span>
        </span>
        <button
          type="button"
          @click="emit('close')"
          class="px-4 py-1.5 rounded-xl font-bold text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 transition cursor-pointer shadow-xs active:scale-95"
        >
          {{ t.feedback.close }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from '../i18n'
import {
  recordDraftFeedback,
  extractDraftFeedbackInsights,
  fetchDraftFeedbacks,
  type DraftFeedbackItem,
  type FeedbackExtractResult,
} from '../services/api'

const props = defineProps<{
  draftId: string
  draftTopic?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'feedback-updated'): void
  (e: 'dna-evolved'): void
}>()

const { t } = useI18n()

const activeTab = ref<'input' | 'records'>('input')
const commentsInput = ref('')
const metrics = ref({
  likes: undefined as number | undefined,
  reads: undefined as number | undefined,
  comments: undefined as number | undefined,
  shares: undefined as number | undefined,
})

const isExtracting = ref(false)
const isSaving = ref(false)
const isLoadingRecords = ref(false)

const toastMsg = ref('')
const toastType = ref<'success' | 'error'>('success')

const latestExtractResult = ref<FeedbackExtractResult | null>(null)
const feedbackRecords = ref<DraftFeedbackItem[]>([])

const applyTemplate = (type: 'resonance' | 'critique') => {
  if (type === 'resonance') {
    commentsInput.value = '这篇文章关于独立开发者「认知资产化」的观点太棒了！长期复利确实是唯一的解法。特别是用沙箱技能和内容分发放大杠杆的提法，醍醐灌顶！希望能多出具体案例。'
    metrics.value.likes = 128
    metrics.value.reads = 2450
    metrics.value.comments = 32
    metrics.value.shares = 45
  } else {
    commentsInput.value = '反思了一下：如果只强调深思熟虑的长期价值，在冷启动期很容易被算法埋没。对于超级个体而言，前期的情绪断层和敏锐痛点是否也是必不可少的生存技能？'
    metrics.value.likes = 85
    metrics.value.reads = 1890
    metrics.value.comments = 24
    metrics.value.shares = 18
  }
}

const loadRecords = async () => {
  if (!props.draftId) return
  isLoadingRecords.value = true
  try {
    feedbackRecords.value = await fetchDraftFeedbacks(props.draftId)
  } catch (err: any) {
    console.warn('Failed to load feedback records', err)
  } finally {
    isLoadingRecords.value = false
  }
}

const switchTab = async (tab: 'input' | 'records') => {
  activeTab.value = tab
  if (tab === 'records') {
    await loadRecords()
  }
}

const handleSaveOnly = async () => {
  if (!commentsInput.value.trim() || !props.draftId) return
  isSaving.value = true
  toastMsg.value = ''
  try {
    const cleanMetrics: Record<string, any> = {}
    if (metrics.value.likes !== undefined) cleanMetrics.likes = metrics.value.likes
    if (metrics.value.reads !== undefined) cleanMetrics.reads = metrics.value.reads
    if (metrics.value.comments !== undefined) cleanMetrics.comments = metrics.value.comments
    if (metrics.value.shares !== undefined) cleanMetrics.shares = metrics.value.shares

    await recordDraftFeedback(props.draftId, commentsInput.value.trim(), cleanMetrics)
    toastMsg.value = t.value.feedback.saveToast
    toastType.value = 'success'
    commentsInput.value = ''
    await loadRecords()
    emit('feedback-updated')
  } catch (err: any) {
    toastMsg.value = err.message || 'Failed to record feedback'
    toastType.value = 'error'
  } finally {
    isSaving.value = false
  }
}

const handleExtractAndEvolve = async () => {
  if (!commentsInput.value.trim() || !props.draftId) return
  isExtracting.value = true
  toastMsg.value = ''
  try {
    const cleanMetrics: Record<string, any> = {}
    if (metrics.value.likes !== undefined) cleanMetrics.likes = metrics.value.likes
    if (metrics.value.reads !== undefined) cleanMetrics.reads = metrics.value.reads
    if (metrics.value.comments !== undefined) cleanMetrics.comments = metrics.value.comments
    if (metrics.value.shares !== undefined) cleanMetrics.shares = metrics.value.shares

    const result = await extractDraftFeedbackInsights(props.draftId, {
      comments_text: commentsInput.value.trim(),
      metrics: cleanMetrics,
    })

    latestExtractResult.value = result
    toastMsg.value = t.value.feedback.successToast
    toastType.value = 'success'
    commentsInput.value = ''
    emit('feedback-updated')
    emit('dna-evolved')
    await loadRecords()
  } catch (err: any) {
    toastMsg.value = err.message || 'Feedback extraction failed'
    toastType.value = 'error'
  } finally {
    isExtracting.value = false
  }
}

const formatDimension = (dim: string) => {
  const map: Record<string, string> = {
    vocabulary: '词汇偏好',
    logic_preference: '论证逻辑',
    core_value: '核心价值观',
    viewpoint_stance: '核心观点主张',
  }
  return map[dim] || dim
}

const formatTime = (ts?: string) => {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

onMounted(async () => {
  await loadRecords()
})
</script>
