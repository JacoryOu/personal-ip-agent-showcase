<template>
  <div class="space-y-6 max-w-6xl mx-auto" @click="handleGlobalClick">
    <!-- Header with Stats -->
    <div class="glass-card border border-slate-200/80 rounded-3xl p-6 shadow-xs relative overflow-hidden scroll-reveal">
      <!-- Background subtle decorative glow -->
      <div class="absolute -top-12 -right-12 w-64 h-64 bg-gradient-to-br from-blue-100/40 via-indigo-100/20 to-transparent rounded-full blur-2xl pointer-events-none"></div>

      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5 relative z-10">
        <div>
          <h2 class="text-2xl font-black tracking-tight text-slate-900 flex items-center gap-2.5">
            <span class="p-1.5 bg-blue-50 rounded-xl text-xl">📚</span>
            <span>{{ t.history.title }}</span>
          </h2>
          <p class="text-sm text-slate-500 mt-1">
            {{ t.history.subtitle }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <!-- JSON Export/Import -->
          <button
            type="button"
            @click="triggerImportFile"
            class="inline-flex items-center justify-center px-3.5 py-2 rounded-xl font-bold text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/80 active:scale-95 transition-all gap-1.5 cursor-pointer shadow-2xs"
            title="Import history from JSON backup"
          >
            <span>📥</span>
            <span>{{ t.history.importJson }}</span>
          </button>
          <input
            ref="fileInputRef"
            type="file"
            accept=".json"
            class="hidden"
            @change="handleFileUpload"
          />

          <button
            type="button"
            :disabled="drafts.length === 0"
            @click="handleExportJson"
            class="inline-flex items-center justify-center px-3.5 py-2 rounded-xl font-bold text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/80 active:scale-95 transition-all gap-1.5 disabled:opacity-50 cursor-pointer shadow-2xs"
            title="Export all drafts as JSON"
          >
            <span>📤</span>
            <span>{{ t.history.exportJson }}</span>
          </button>

          <button
            type="button"
            @click="$emit('new-creation')"
            class="inline-flex items-center justify-center px-4 py-2 rounded-xl font-bold text-xs bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs active:scale-95 transition-all gap-1.5 cursor-pointer"
          >
            <span>✍️</span>
            <span>{{ t.history.newCreation }}</span>
          </button>
        </div>
      </div>

      <!-- Quick Metrics Counters -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3.5 pt-5 relative z-10">
        <div class="bg-slate-50/70 hover:bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{{ t.history.totalCount }}</div>
          <div class="text-2xl font-black text-slate-800 mt-0.5">{{ drafts.length }}</div>
        </div>

        <div class="bg-blue-50/60 hover:bg-blue-50 border border-blue-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-blue-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>📝</span>
            <span>{{ t.history.totalWords }}</span>
          </div>
          <div class="text-2xl font-black text-blue-900 mt-0.5">{{ totalWordsCount.toLocaleString() }}</div>
        </div>

        <div class="bg-amber-50/60 hover:bg-amber-50 border border-amber-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-amber-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>🦴</span>
            <span>{{ t.history.blueprintWorks }}</span>
          </div>
          <div class="text-2xl font-black text-amber-900 mt-0.5">{{ blueprintDraftsCount }}</div>
        </div>

        <div class="bg-purple-50/60 hover:bg-purple-50 border border-purple-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-purple-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>🧬</span>
            <span>{{ t.history.latestArchive }}</span>
          </div>
          <div class="text-xs font-bold text-purple-900 mt-2 truncate">{{ latestDraftTime }}</div>
        </div>
      </div>
    </div>

    <!-- Search & Filter Toolbar -->
    <div class="glass-card border border-slate-200/80 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-3 scroll-reveal">
      <div class="flex items-center gap-2 flex-1 sm:max-w-md">
        <span class="text-slate-400">🔍</span>
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t.history.searchPlaceholder"
          class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div class="flex items-center gap-2">
        <select
          v-model="sortBy"
          class="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
        >
          <option value="newest">{{ t.history.sortNewest }}</option>
          <option value="oldest">{{ t.history.sortOldest }}</option>
          <option value="words">{{ t.history.sortWords }}</option>
        </select>
        <button
          v-if="drafts.length > 0"
          type="button"
          @click="refreshDrafts"
          class="p-2 text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl transition cursor-pointer active:scale-95"
          title="Refresh"
        >
          🔄
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="filteredDrafts.length === 0" class="text-center py-16 bg-white border border-slate-200 rounded-3xl p-6 scroll-fade">
      <div class="text-4xl mb-3">📁</div>
      <h3 class="text-base font-bold text-slate-700">{{ t.history.emptyTitle }}</h3>
      <p class="text-xs text-slate-400 mt-1 max-w-md mx-auto">
        {{ t.history.emptyDesc }}
      </p>
      <button
        type="button"
        @click="$emit('new-creation')"
        class="mt-4 px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition active:scale-95 cursor-pointer"
      >
        {{ t.history.startFirstCreation }}
      </button>
    </div>

    <!-- Drafts Grid (Requirement 2: Clean layout, Word count badge, Creation date, Source material lineage badge) -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4 cv-auto">
      <div
        v-for="draft in filteredDrafts"
        :key="draft.id"
        class="bg-white border border-slate-200/90 rounded-3xl p-5 sm:p-6 shadow-xs flex flex-col justify-between hover:shadow-md hover:border-slate-300 transition-all duration-200 space-y-4 relative group scroll-reveal active:scale-[0.99]"
      >
        <div class="space-y-3.5">
          <!-- Card Header Badges (Word count badge, Creation date, Source material lineage badge) -->
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-1.5 flex-wrap">
              <!-- Source Material Lineage Badge (Requirement 2) -->
              <span
                v-if="draft.source_material_id || draft.lineage_snapshot?.source_material_title"
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200/80 shadow-2xs"
                :title="`溯源标杆/热点素材：${getLineageTitle(draft)}`"
              >
                <span>🌱</span>
                <span>溯源：{{ getLineageTitle(draft) }}</span>
              </span>

              <!-- Blueprint Lineage Badge -->
              <span
                v-else-if="draft.blueprint_title"
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200/80 shadow-2xs"
              >
                <span>🦴</span>
                <span>骨架：{{ draft.blueprint_title }}</span>
              </span>

              <!-- Original Idea Badge -->
              <span
                v-else
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200/80 shadow-2xs"
              >
                <span>✨</span>
                <span>纯原创灵感</span>
              </span>

              <!-- Creation Date Badge (Requirement 2) -->
              <span class="text-[10px] text-slate-400 font-mono flex items-center gap-1 bg-slate-50 px-2 py-0.5 rounded-md border border-slate-100">
                <span>🕒</span>
                <span>{{ formatDateTime(draft.created_at) }}</span>
              </span>
            </div>

            <!-- Word Count Badge (Requirement 2) -->
            <span class="text-[10px] font-bold text-slate-700 font-mono bg-slate-100/90 border border-slate-200/70 px-2.5 py-1 rounded-lg shadow-2xs">
              ~{{ draft.word_count || draft.content.length }} {{ t.editor.words }}
            </span>
          </div>

          <!-- Topic / Headline -->
          <h3
            @click="openPreview(draft)"
            class="text-base font-black text-slate-900 leading-snug line-clamp-2 hover:text-indigo-600 transition cursor-pointer"
            title="点击预览全文"
          >
            {{ draft.topic }}
          </h3>

          <!-- Summary / Content Snippet -->
          <div class="bg-slate-50/80 p-3 rounded-2xl border border-slate-100/90 space-y-1.5">
            <p class="text-xs text-slate-600 leading-relaxed line-clamp-3 font-sans">
              {{ draft.summary || draft.content.replace(/[#*`>-]/g, '').slice(0, 160) }}...
            </p>

            <!-- Micro Tags if present -->
            <div v-if="draft.tags && draft.tags.length > 0" class="flex flex-wrap items-center gap-1 pt-1 border-t border-slate-200/50">
              <span
                v-for="tag in draft.tags"
                :key="tag"
                class="text-[9px] font-semibold text-slate-500 bg-white px-1.5 py-0.5 rounded-md border border-slate-200/60"
              >
                #{{ tag }}
              </span>
            </div>
          </div>
        </div>

        <!-- Card Action Footer (Requirement 2: Refined Primary Actions with Icons + Clean Secondary Dropdown) -->
        <div class="border-t border-slate-100 mt-4 pt-3 flex items-center justify-between gap-2">
          <!-- Primary Actions (继续编辑, 一鱼多吃分发, 录入反馈) -->
          <div class="flex items-center gap-2 flex-wrap">
            <!-- 1. 继续编辑 -->
            <button
              type="button"
              @click="$emit('load-draft', draft)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-blue-700 bg-blue-50/80 hover:bg-blue-100 border border-blue-200 shadow-2xs active:scale-95 transition cursor-pointer"
              title="载入工坊第3步继续精修"
            >
              <span>🔄</span>
              <span>继续编辑</span>
            </button>

            <!-- 2. 一鱼多吃分发 -->
            <button
              type="button"
              @click="$emit('distribute-draft', draft)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-indigo-700 bg-indigo-50/80 hover:bg-indigo-100 border border-indigo-200 shadow-2xs active:scale-95 transition cursor-pointer"
              title="一键多平台自适应排版与分发"
            >
              <span>🐟</span>
              <span>{{ t.history.distributeAction }}</span>
            </button>

            <!-- 3. 录入反馈 -->
            <button
              type="button"
              @click="selectedFeedbackDraft = draft"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-purple-700 bg-purple-50/80 hover:bg-purple-100 border border-purple-200 shadow-2xs active:scale-95 transition cursor-pointer"
              :title="t.history.feedbackBtn"
            >
              <span>📊</span>
              <span>录入反馈</span>
            </button>
          </div>

          <!-- Secondary Actions (Clean Dropdown to Eliminate Clutter) -->
          <div class="relative" @click.stop>
            <button
              type="button"
              @click="toggleDropdown(draft.id)"
              class="p-1.5 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-100 transition cursor-pointer active:scale-95 border border-transparent hover:border-slate-200"
              title="更多操作"
            >
              <span class="font-bold text-sm tracking-widest">···</span>
            </button>

            <!-- Dropdown Menu -->
            <div
              v-if="activeDropdownId === draft.id"
              class="absolute right-0 bottom-full mb-2 w-44 bg-white rounded-2xl shadow-xl border border-slate-200 py-1.5 z-30 animate-in fade-in zoom-in-95 duration-100 space-y-0.5"
            >
              <button
                type="button"
                @click="openPreview(draft); activeDropdownId = null"
                class="w-full px-3.5 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer transition"
              >
                <span>👁️</span>
                <span>沉浸全文预览</span>
              </button>
              <button
                type="button"
                @click="copyText(draft.content); activeDropdownId = null"
                class="w-full px-3.5 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer transition"
              >
                <span>📋</span>
                <span>快速复制正文</span>
              </button>
              <button
                type="button"
                @click="downloadMarkdown(draft); activeDropdownId = null"
                class="w-full px-3.5 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer transition"
              >
                <span>📥</span>
                <span>导出 Markdown</span>
              </button>
              <div class="border-t border-slate-100 my-1"></div>
              <button
                type="button"
                @click="confirmDelete(draft.id); activeDropdownId = null"
                class="w-full px-3.5 py-2 text-left text-xs font-medium text-rose-600 hover:bg-rose-50 flex items-center gap-2 cursor-pointer transition"
              >
                <span>🗑️</span>
                <span>删除此篇归档</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Fullscreen / Reader Modal for Draft Preview -->
    <div
      v-if="previewDraft"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
    >
      <div class="bg-white rounded-3xl max-w-3xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 my-8 max-h-[88vh] flex flex-col toast-enter">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-xs font-bold text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                {{ previewDraft.blueprint_title ? '🦴 骨架长文' : '✍️ 原创草稿' }}
              </span>
              <span class="text-xs text-slate-400 font-mono">{{ formatDateTime(previewDraft.created_at) }}</span>
            </div>
            <h3 class="text-xl font-black text-slate-900 mt-1">{{ previewDraft.topic }}</h3>
          </div>
          <button @click="previewDraft = null" class="text-slate-400 hover:text-slate-600 font-bold text-xl cursor-pointer">✕</button>
        </div>

        <!-- Article Reader Area -->
        <div class="flex-1 overflow-y-auto pr-2 space-y-4 text-slate-800 text-sm leading-relaxed font-sans select-text whitespace-pre-wrap">
          {{ previewDraft.content }}
        </div>

        <!-- Reader Footer -->
        <div class="border-t border-slate-100 pt-3 flex items-center justify-between">
          <span class="text-xs text-slate-400 font-mono">
            {{ previewDraft.content.length }} 字符 · ~{{ previewDraft.word_count || previewDraft.content.length }} 字 · 约需 {{ Math.max(1, Math.ceil((previewDraft.word_count || previewDraft.content.length) / 300)) }} 分钟阅读
          </span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="copyText(previewDraft.content)"
              class="px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition cursor-pointer active:scale-95"
            >
              {{ copied ? '✓ 已复制全文' : '复制全文' }}
            </button>
            <button
              type="button"
              @click="$emit('load-draft', previewDraft); previewDraft = null"
              class="px-4 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition shadow-xs active:scale-95 cursor-pointer flex items-center gap-1.5"
            >
              <span>🔄</span>
              <span>载入工坊继续创作</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Audience Feedback & Cognitive DNA Evolution Modal (Phase 4) -->
    <FeedbackModal
      v-if="selectedFeedbackDraft"
      :draft-id="selectedFeedbackDraft.id"
      :draft-topic="selectedFeedbackDraft.topic"
      @close="selectedFeedbackDraft = null"
      @dna-evolved="refreshDrafts"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from '../i18n'
import FeedbackModal from './FeedbackModal.vue'
import {
  getLocalDrafts,
  setLocalDrafts,
  getAllHistoryDrafts,
  deleteDraftFromArchive,
  exportHistoryAsJson,
  importHistoryFromJson,
  type HistoryDraftItem,
} from '../services/historyStorage'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'load-draft', draft: HistoryDraftItem): void
  (e: 'distribute-draft', draft: HistoryDraftItem): void
  (e: 'new-creation'): void
}>()

const drafts = ref<HistoryDraftItem[]>([])
const selectedFeedbackDraft = ref<HistoryDraftItem | null>(null)
const searchQuery = ref('')
const sortBy = ref<'newest' | 'oldest' | 'words'>('newest')
const previewDraft = ref<HistoryDraftItem | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const copied = ref(false)
const activeDropdownId = ref<string | null>(null)

const toggleDropdown = (id: string) => {
  activeDropdownId.value = activeDropdownId.value === id ? null : id
}

const handleGlobalClick = () => {
  activeDropdownId.value = null
}

const refreshDrafts = async () => {
  drafts.value = await getAllHistoryDrafts()
}

onMounted(async () => {
  const urlParams = new URLSearchParams(window.location.search)
  if (urlParams.get('seed') === '1' && getLocalDrafts().length === 0) {
    setLocalDrafts([
      {
        id: 'draft_demo_01',
        topic: '独立开发者的超级个体跃迁模型：如何打造个人商业复利',
        content: '# 独立开发者的超级个体跃迁模型\n\n真正拉开超级个体差距的，从来不是代码产出效率，而是认知杠杆的复合积累。\n\n## 1. 认知资产化\n\n坚持长期主义，拒绝低效内卷，在行动中穿透迷雾，直击商业本质。把每一次思考沉淀为可复用的知识模型。\n\n## 2. 杠杆效应放大\n\n通过内容分发与自动化沙箱技能，让你的思维资产 7x24 小时为你工作。',
        original_draft: '# 独立开发者的超级个体跃迁模型\n\n本文将探讨独立开发者如何通过代码与内容构建商业杠杆。',
        summary: '解析独立开发者的认知资产化逻辑与一人公司杠杆模型，探讨反内卷与长期主义。',
        blueprint_title: '爆款拆骨·非共识商业洞察',
        blueprint_id: 'bp_demo_01',
        word_count: 850,
        created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
        updated_at: new Date().toISOString(),
        tags: ['个人商业', '超级个体', '认知资产'],
      },
    ])
  }
  await refreshDrafts()
})

const totalWordsCount = computed(() => {
  return drafts.value.reduce((acc, d) => acc + (d.word_count || d.content.length || 0), 0)
})

const blueprintDraftsCount = computed(() => {
  return drafts.value.filter((d) => !!d.blueprint_title).length
})

const latestDraftTime = computed(() => {
  if (drafts.value.length === 0) return '无'
  const latest = drafts.value[0]
  return formatDateTime(latest.created_at)
})

const getLineageTitle = (draft: HistoryDraftItem): string => {
  if (draft.lineage_snapshot?.source_material_title) {
    const raw = String(draft.lineage_snapshot.source_material_title)
    return raw.length > 14 ? raw.slice(0, 14) + '...' : raw
  }
  if (draft.source_material_id) {
    return '已绑定素材'
  }
  return '原创'
}

const filteredDrafts = computed(() => {
  let list = [...drafts.value]
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim()
    list = list.filter(
      (d) =>
        d.topic.toLowerCase().includes(q) ||
        d.content.toLowerCase().includes(q) ||
        (d.summary && d.summary.toLowerCase().includes(q))
    )
  }

  if (sortBy.value === 'newest') {
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  } else if (sortBy.value === 'oldest') {
    list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
  } else if (sortBy.value === 'words') {
    list.sort((a, b) => (b.word_count || b.content.length) - (a.word_count || a.content.length))
  }
  return list
})

function formatDateTime(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

function openPreview(draft: HistoryDraftItem) {
  previewDraft.value = draft
}

async function confirmDelete(id: string) {
  if (window.confirm('确定要删除这篇创作历史记录吗？删除后不可恢复。')) {
    await deleteDraftFromArchive(id)
    await refreshDrafts()
  }
}

function downloadMarkdown(draft: HistoryDraftItem) {
  const blob = new Blob([`# ${draft.topic}\n\n${draft.content}`], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  const safeName = (draft.topic.slice(0, 30) || 'draft').replace(/[\\/:*?"<>|]/g, '_')
  a.download = `${safeName}.md`
  a.click()
  a.remove()
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // fallback
  }
}

function handleExportJson() {
  exportHistoryAsJson(drafts.value)
}

function triggerImportFile() {
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
    fileInputRef.value.click()
  }
}

async function handleFileUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const count = importHistoryFromJson(text)
    alert(`成功导入 ${count} 篇历史创作归档！`)
    await refreshDrafts()
  } catch (err: any) {
    alert(err.message || '导入失败，请检查文件格式。')
  }
}

defineExpose({
  refreshDrafts,
})
</script>
