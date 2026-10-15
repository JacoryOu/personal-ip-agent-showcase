<template>
  <div class="space-y-6 max-w-4xl mx-auto scroll-reveal">
    <!-- Top Result Banner -->
    <div class="bg-white rounded-2xl shadow-xl border border-slate-200/80 overflow-hidden scroll-reveal">
      <!-- Dark Hero Banner with High Contrast -->
      <div class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-6 sm:p-8 text-white relative overflow-hidden">
        <div class="absolute -right-12 -top-12 w-64 h-64 rounded-full bg-purple-500/10 blur-3xl pointer-events-none"></div>
        <div class="absolute -left-12 -bottom-12 w-64 h-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none"></div>

        <div class="flex flex-wrap items-center justify-between gap-6 relative z-10">
          <div class="space-y-2.5 max-w-xl">
            <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-400/30 backdrop-blur-md shadow-2xs">
              <span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>
              <span>🧬 {{ t.dna.hasDiffBadge }}</span>
            </div>
            <h2 class="text-2xl sm:text-3xl font-black tracking-tight text-white">{{ t.dna.title }}</h2>
            <p class="text-slate-300 text-xs sm:text-sm leading-relaxed">
              {{ t.dna.subtitle }}
              <strong class="text-white block mt-1 font-semibold text-sm sm:text-base">"{{ topic }}"</strong>
            </p>
          </div>

          <!-- Quick Action Toolbar: Prominent Distribution & Feedback Buttons -->
          <div class="flex items-center flex-wrap gap-2.5">
            <!-- 🐟 一鱼多吃全网分发 -->
            <button
              type="button"
              @click="triggerDistribute"
              class="px-4 py-2.5 text-xs font-bold rounded-xl bg-gradient-to-r from-indigo-500 via-blue-600 to-indigo-600 hover:from-indigo-600 hover:to-blue-700 text-white shadow-md hover:shadow-lg transition-all flex items-center space-x-1.5 cursor-pointer active:scale-95"
            >
              <span class="text-sm">🐟</span>
              <span>{{ t.distribute.button }}</span>
            </button>

            <!-- 📊 录入发布反馈 -->
            <button
              type="button"
              @click="triggerOpenFeedback"
              class="px-4 py-2.5 text-xs font-bold rounded-xl bg-gradient-to-r from-purple-600 via-fuchsia-600 to-purple-600 hover:from-purple-700 hover:to-fuchsia-700 text-white shadow-md hover:shadow-lg transition-all flex items-center space-x-1.5 cursor-pointer active:scale-95"
              :title="t.history.feedbackBtn"
            >
              <span class="text-sm">📊</span>
              <span>{{ t.history.feedbackBtn }}</span>
            </button>

            <!-- 📋 复制 DNA 画像 -->
            <button
              type="button"
              @click="copyDNASummary"
              class="px-3.5 py-2.5 text-xs font-semibold rounded-xl bg-white/10 hover:bg-white/20 text-white border border-white/20 transition-all backdrop-blur-md cursor-pointer active:scale-95"
            >
              <span>{{ copied ? '✓ ' + t.dna.copyProfileSuccess : '📋 ' + t.dna.copyProfile }}</span>
            </button>

            <!-- + 开启新选题 -->
            <button
              type="button"
              @click="triggerNewTopic"
              class="px-4 py-2.5 text-xs font-bold rounded-xl bg-white text-slate-900 hover:bg-slate-100 shadow-md transition-all cursor-pointer active:scale-95"
            >
              + {{ t.dna.startNew }}
            </button>
          </div>
        </div>
      </div>

      <!-- Zero-Diff Notice if identical -->
      <div v-if="!dnaOutput.has_diff" class="p-8 sm:p-10 text-center space-y-4 bg-amber-50/50">
        <div class="text-4xl animate-bounce">⚖️</div>
        <h3 class="text-lg font-bold text-slate-900">{{ t.dna.zeroDiffBadge }}</h3>
        <p class="text-slate-600 text-xs sm:text-sm max-w-lg mx-auto leading-relaxed">
          {{ t.dna.zeroDiffDesc }}
        </p>
        <div>
          <button
            type="button"
            @click="triggerReEditDraft"
            class="px-5 py-2.5 bg-indigo-600 text-white font-bold text-xs sm:text-sm rounded-xl hover:bg-indigo-700 shadow-md transition-all cursor-pointer active:scale-95"
          >
            {{ t.dna.backToEdit }}
          </button>
        </div>
      </div>

      <!-- Diff Summary Callout & 4 Dimension Visual Cards -->
      <div v-else class="p-5 sm:p-7 space-y-6">
        <!-- Diff Summary Callout -->
        <div v-if="dnaOutput.diff_summary" class="p-4 sm:p-5 bg-gradient-to-r from-purple-50/90 via-indigo-50/70 to-purple-50/90 border border-purple-200/80 rounded-2xl flex items-start space-x-3.5 shadow-2xs">
          <div class="w-8 h-8 rounded-xl bg-purple-600 text-white flex items-center justify-center text-sm shadow-2xs font-bold shrink-0 mt-0.5">
            🔍
          </div>
          <div>
            <h4 class="text-xs font-black uppercase tracking-wider text-purple-950 mb-1">
              {{ t.dna.summaryTitle }}
            </h4>
            <p class="text-xs sm:text-sm text-purple-900 leading-relaxed font-medium">
              {{ dnaOutput.diff_summary }}
            </p>
          </div>
        </div>

        <!-- 4 Dimension Visual DNA Cards Grid (Vocabulary, Logic, Values, Taboos) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
          <!-- Dimension 1: Vocabulary & Phrasing -->
          <div class="bg-slate-50/70 rounded-2xl p-5 border border-slate-200/80 space-y-3.5 shadow-2xs hover:shadow-xs transition">
            <div class="flex items-center justify-between border-b border-slate-200/80 pb-3">
              <div class="flex items-center space-x-2.5">
                <span class="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold">📝</span>
                <div>
                  <h3 class="text-xs font-bold text-slate-900">{{ t.dna.vocabularyTitle }}</h3>
                  <span class="text-[10px] text-slate-400 font-medium">语言质感 · 句式习惯</span>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100/80 text-blue-800 border border-blue-200">
                {{ vocabularyHabits.length }} 条特征
              </span>
            </div>
            <div v-if="vocabularyHabits.length" class="space-y-2">
              <div
                v-for="(item, idx) in vocabularyHabits"
                :key="idx"
                class="p-3 bg-white rounded-xl border border-slate-200/70 text-xs font-medium text-slate-800 shadow-2xs leading-relaxed flex items-start gap-2"
              >
                <span class="text-blue-500 font-bold">“</span>
                <span class="flex-1">{{ item }}</span>
                <span class="text-blue-500 font-bold">”</span>
              </div>
            </div>
            <p v-else class="text-xs text-slate-400 italic py-2">{{ t.dna.emptyTags }}</p>
          </div>

          <!-- Dimension 2: Logic & Structural Flow -->
          <div class="bg-slate-50/70 rounded-2xl p-5 border border-slate-200/80 space-y-3.5 shadow-2xs hover:shadow-xs transition">
            <div class="flex items-center justify-between border-b border-slate-200/80 pb-3">
              <div class="flex items-center space-x-2.5">
                <span class="w-7 h-7 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center text-sm font-bold">🧠</span>
                <div>
                  <h3 class="text-xs font-bold text-slate-900">{{ t.dna.logicTitle }}</h3>
                  <span class="text-[10px] text-slate-400 font-medium">论证推演 · 结构节奏</span>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100/80 text-amber-800 border border-amber-200">
                {{ logicPreferences.length }} 条规则
              </span>
            </div>
            <div v-if="logicPreferences.length" class="space-y-2">
              <div
                v-for="(item, idx) in logicPreferences"
                :key="idx"
                class="p-3 bg-white rounded-xl border border-slate-200/70 text-xs font-medium text-slate-800 shadow-2xs leading-relaxed flex items-start gap-2"
              >
                <span class="text-amber-500 font-bold">↳</span>
                <span class="flex-1">{{ item }}</span>
              </div>
            </div>
            <p v-else class="text-xs text-slate-400 italic py-2">{{ t.dna.emptyTags }}</p>
          </div>

          <!-- Dimension 3: Core Values & Beliefs -->
          <div class="bg-slate-50/70 rounded-2xl p-5 border border-slate-200/80 space-y-3.5 shadow-2xs hover:shadow-xs transition">
            <div class="flex items-center justify-between border-b border-slate-200/80 pb-3">
              <div class="flex items-center space-x-2.5">
                <span class="w-7 h-7 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center text-sm font-bold">💎</span>
                <div>
                  <h3 class="text-xs font-bold text-slate-900">{{ t.dna.valuesTitle }}</h3>
                  <span class="text-[10px] text-slate-400 font-medium">底层主张 · 价值坐标</span>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100/80 text-purple-800 border border-purple-200">
                {{ coreValues.length }} 条取向
              </span>
            </div>
            <div v-if="coreValues.length" class="space-y-2">
              <div
                v-for="(item, idx) in coreValues"
                :key="idx"
                class="p-3 bg-white rounded-xl border border-slate-200/70 text-xs font-medium text-slate-800 shadow-2xs leading-relaxed flex items-start gap-2"
              >
                <span class="text-purple-500 font-bold">★</span>
                <span class="flex-1">{{ item }}</span>
              </div>
            </div>
            <p v-else class="text-xs text-slate-400 italic py-2">{{ t.dna.emptyTags }}</p>
          </div>

          <!-- Dimension 4: Taboos & Negative Constraints -->
          <div class="bg-slate-50/70 rounded-2xl p-5 border border-slate-200/80 space-y-3.5 shadow-2xs hover:shadow-xs transition">
            <div class="flex items-center justify-between border-b border-slate-200/80 pb-3">
              <div class="flex items-center space-x-2.5">
                <span class="w-7 h-7 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center text-sm font-bold">🚫</span>
                <div>
                  <h3 class="text-xs font-bold text-slate-900">表达禁忌与反向约束 (Taboos DNA)</h3>
                  <span class="text-[10px] text-slate-400 font-medium">剔除表达 · 规避套话</span>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100/80 text-rose-800 border border-rose-200">
                {{ tabooHabits.length }} 条红线
              </span>
            </div>
            <div v-if="tabooHabits.length" class="space-y-2">
              <div
                v-for="(item, idx) in tabooHabits"
                :key="idx"
                class="p-3 bg-white rounded-xl border border-rose-200/70 text-xs font-medium text-rose-950 shadow-2xs leading-relaxed flex items-start gap-2"
              >
                <span class="text-rose-500 font-bold">✕</span>
                <span class="flex-1">{{ item }}</span>
              </div>
            </div>
            <p v-else class="text-xs text-slate-400 italic py-2">{{ t.dna.emptyTags }}</p>
          </div>
        </div>

        <!-- Holistic Cognitive Style Summary -->
        <div v-if="dnaOutput.thinking_dna?.summary" class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 sm:p-7 rounded-2xl space-y-2.5 shadow-md relative overflow-hidden">
          <div class="flex items-center space-x-2 text-purple-400 text-xs font-bold uppercase tracking-wider">
            <span>✨ {{ t.dna.summaryTitle }}</span>
          </div>
          <p class="text-xs sm:text-sm leading-relaxed text-slate-200 font-serif italic">
            "{{ dnaOutput.thinking_dna.summary }}"
          </p>
        </div>

        <!-- Persistence Confirmation Pill -->
        <div v-if="dnaOutput.dna_record_id" class="p-3.5 rounded-xl bg-emerald-50/90 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between flex-wrap gap-2 shadow-2xs">
          <div class="flex items-center space-x-2">
            <span class="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">✓</span>
            <span>已持久化保存至个人认知记忆库 (ID: <code class="font-mono text-[11px] bg-emerald-100/80 px-1.5 py-0.5 rounded text-emerald-900">{{ dnaOutput.dna_record_id }}</code>)</span>
          </div>
          <span class="text-[10px] text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-full font-bold uppercase border border-emerald-200">
            V0.1 Progressive Evolution
          </span>
        </div>
      </div>

      <!-- Footer Bar -->
      <div class="bg-slate-50/90 border-t border-slate-200/80 p-4 sm:p-5 px-6 flex items-center justify-between flex-wrap gap-3">
        <button
          type="button"
          @click="triggerReEditDraft"
          class="text-xs sm:text-sm font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer active:scale-95 transition"
        >
          {{ t.dna.backToEdit }}
        </button>
        <button
          type="button"
          @click="triggerNewTopic"
          class="px-5 py-2.5 text-xs sm:text-sm font-bold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 shadow-md transition-all cursor-pointer active:scale-95"
        >
          {{ t.dna.startNew }} →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { DNAExtractionOutput } from '../services/api'
import { useI18n } from '../i18n'

const { t } = useI18n()

const props = defineProps<{
  dnaOutput: DNAExtractionOutput
  topic: string
}>()

const emit = defineEmits<{
  (e: 'reEditDraft'): void
  (e: 're-edit-draft'): void
  (e: 'newTopic'): void
  (e: 'new-topic'): void
  (e: 'distribute'): void
  (e: 'openFeedback'): void
  (e: 'open-feedback'): void
}>()

function triggerDistribute() {
  emit('distribute')
}

function triggerOpenFeedback() {
  emit('openFeedback')
  emit('open-feedback')
}

function triggerReEditDraft() {
  emit('reEditDraft')
  emit('re-edit-draft')
}

function triggerNewTopic() {
  emit('newTopic')
  emit('new-topic')
}

const copied = ref(false)

const vocabularyHabits = computed(() => {
  return props.dnaOutput.thinking_dna?.vocabulary_habits || []
})

const logicPreferences = computed(() => {
  return props.dnaOutput.thinking_dna?.logic_preferences || []
})

const coreValues = computed(() => {
  return props.dnaOutput.thinking_dna?.core_values || []
})

const tabooHabits = computed(() => {
  const d = props.dnaOutput.thinking_dna as any
  if (d?.taboos && Array.isArray(d.taboos) && d.taboos.length > 0) {
    return d.taboos
  }
  const negativeRegex = /避免|拒绝|不要|禁止|严禁|摒弃|反感|戒掉|不使用|少用|去除|慎用|杜绝|剔除|否定|警惕|不用|内卷/i
  const allStatements = [
    ...(d?.vocabulary_habits || []),
    ...(d?.logic_preferences || []),
    ...(d?.core_values || []),
  ]
  const matched = allStatements.filter((item: string) => negativeRegex.test(item))
  if (matched.length > 0) {
    return Array.from(new Set(matched))
  }
  return [
    '拒绝空洞堆砌与行业公关套话，坚持用白话剖析本质',
    '避免无事实论据支撑的自嗨式论断，用实战推导替代情绪煽动',
    '摒弃冗长的起承转合铺垫，开门见山直击核心痛点与冲突',
  ]
})

const copyDNASummary = async () => {
  const d = props.dnaOutput.thinking_dna
  if (!d) return

  const text = [
    `=== Thinking DNA Profile for: ${props.topic} ===`,
    props.dnaOutput.diff_summary ? `Editorial Diff: ${props.dnaOutput.diff_summary}` : '',
    '\n[Vocabulary & Tone Habits]',
    ...vocabularyHabits.value.map((v) => `- ${v}`),
    '\n[Logic & Flow Preferences]',
    ...logicPreferences.value.map((l) => `- ${l}`),
    '\n[Core Values & Stance]',
    ...coreValues.value.map((c) => `- ${c}`),
    '\n[Taboos & Negative Guardrails]',
    ...tabooHabits.value.map((item: string) => `- ${item}`),
    d.summary ? `\n[Holistic Synthesis]\n${d.summary}` : '',
  ]
    .filter(Boolean)
    .join('\n')

  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2500)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2500)
  }
}
</script>
