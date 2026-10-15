<template>
  <div class="min-h-screen bg-slate-50/60 text-slate-800 relative selection:bg-indigo-500 selection:text-white overflow-x-clip">
    <!-- Ambient Atmosphere Glow -->
    <div
      class="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[360px] bg-gradient-to-b from-indigo-200/30 via-purple-100/20 to-transparent blur-3xl -z-10"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute top-48 right-0 w-[450px] h-[320px] bg-gradient-to-bl from-blue-100/20 via-indigo-50/15 to-transparent blur-3xl -z-10"
      aria-hidden="true"
    ></div>

    <!-- Sticky Glassmorphic Header -->
    <header class="sticky top-0 z-40 backdrop-blur-md bg-white/80 border-b border-slate-200/60 shadow-2xs">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="h-16 flex items-center justify-between gap-3">
          <!-- Left: Brand Identity -->
          <div class="flex items-center space-x-3 select-none">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-sm ring-1 ring-black/5 text-base font-bold">
              <span>⚡</span>
            </div>
            <div class="flex items-center space-x-2">
              <span class="font-bold text-slate-900 tracking-tight text-base sm:text-lg">
                {{ t.app.title }}
              </span>
              <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/60">
                Cognitive Studio
              </span>
            </div>
          </div>

          <!-- Right: Control Capsule Island -->
          <div class="flex items-center gap-1.5 sm:gap-2 p-1 bg-slate-100/80 rounded-full border border-slate-200/60 shadow-2xs backdrop-blur-xs">
            <!-- Daily Briefing Notification Pill -->
            <button
              type="button"
              @click="isBriefingModalOpen = true"
              class="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-bold transition-all shadow-2xs active:scale-95 cursor-pointer relative"
              :class="
                briefingInfo?.unread
                  ? 'bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 text-white shadow-sm shadow-orange-500/25 ring-2 ring-orange-300 animate-pulse'
                  : 'bg-white border border-slate-200/80 text-slate-700 hover:bg-slate-50 hover:text-slate-900'
              "
              :title="briefingInfo?.unread ? t.briefing.unreadPill : t.briefing.pillEmpty"
            >
              <span class="text-sm">📬</span>
              <span class="hidden sm:inline">
                {{ briefingButtonText }}
              </span>
              <span class="sm:hidden">
                {{ briefingInfo?.unread ? `早报(${briefingInfo.total_items})` : '早报' }}
              </span>
              <span
                v-if="briefingInfo?.unread"
                class="absolute -top-1 -right-1 flex h-3 w-3"
              >
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
              </span>
            </button>

            <!-- Visual Model Switcher Pill -->
            <ModelSelectorPill @open-settings="isSettingsModalOpen = true" />

            <!-- Language Switcher Pill -->
            <button
              type="button"
              @click="toggleLocale"
              class="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-white border border-slate-200/80 shadow-2xs text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all active:scale-95 cursor-pointer"
              title="Toggle Language / 切换语言"
            >
              <span class="text-sm">🌐</span>
              <span class="hidden md:inline">{{ locale === 'zh' ? 'English' : '简体中文' }}</span>
              <span class="md:hidden uppercase font-bold text-[10px]">{{ locale === 'zh' ? 'EN' : '中' }}</span>
            </button>

            <!-- Backend Status Indicator -->
            <div
              class="inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium transition-colors"
              :class="backendConnected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80' : 'bg-amber-50 text-amber-700 border border-amber-200/80'"
              :title="backendStatusText"
            >
              <span class="relative flex h-2 w-2">
                <span v-if="backendConnected" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2" :class="backendConnected ? 'bg-emerald-500' : 'bg-amber-500'"></span>
              </span>
              <span class="hidden lg:inline">{{ backendConnected ? t.app.backendOnline : t.app.backendOffline }}</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Workspace Body -->
    <main class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <!-- Ambient Hero Banner -->
      <div class="text-center space-y-2 pt-2">
        <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
          {{ t.app.title }}
        </h1>
        <p class="text-slate-500 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
          {{ t.app.subtitle }}
        </p>
      </div>

      <!-- Segmented Nav Tabs -->
      <div class="flex items-center justify-center">
        <nav class="inline-flex items-center gap-1 sm:gap-1.5 bg-slate-100/80 p-1.5 rounded-2xl border border-slate-200/60 shadow-inner backdrop-blur-xs max-w-full overflow-x-auto">
          <!-- TAB 1: STUDIO VIEW (WORKBENCH) -->
          <button
            type="button"
            @click="switchTab('studio')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95"
            :class="
              activeTab === 'studio'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">✍️</span>
            <span>{{ t.tabs.studio }}</span>
          </button>

          <!-- TAB: PRIVATE DOMAIN HUB -->
          <button
            type="button"
            @click="switchTab('private_domain')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95"
            :class="
              activeTab === 'private_domain'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">📱</span>
            <span>{{ t.tabs.private_domain }}</span>
          </button>

          <!-- TAB: COGNITIVE CHAT LOUNGE -->
          <button
            type="button"
            @click="switchTab('chat_lounge')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95"
            :class="
              activeTab === 'chat_lounge'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">💬</span>
            <span>{{ t.tabs.chat_lounge }}</span>
          </button>

          <!-- TAB 2: MATERIAL VAULT -->
          <button
            type="button"
            @click="switchTab('vault')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95"
            :class="
              activeTab === 'vault'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">🗄️</span>
            <span>{{ t.tabs.vault }}</span>
          </button>

          <!-- TAB 3: COGNITIVE PROFILE DASHBOARD -->
          <button
            type="button"
            @click="switchTab('profile')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95 relative"
            :class="
              activeTab === 'profile'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">🧠</span>
            <span>{{ t.tabs.profile }}</span>
            <span
              v-if="activeTraitsCount > 0"
              class="px-1.5 py-0.5 rounded-full text-[10px] font-extrabold transition-colors leading-none"
              :class="activeTab === 'profile' ? 'bg-purple-100 text-purple-700 border border-purple-200' : 'bg-slate-200/80 text-slate-600'"
            >
              {{ activeTraitsCount }}
            </span>
          </button>

          <!-- TAB 4: CREATION HISTORY & ARCHIVE (MODULE 1) -->
          <button
            type="button"
            @click="switchTab('history')"
            class="inline-flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-200 cursor-pointer select-none whitespace-nowrap active:scale-95 relative"
            :class="
              activeTab === 'history'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50 scale-[1.02] font-bold tab-active-glow'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 border border-transparent font-medium'
            "
          >
            <span class="text-base leading-none">📚</span>
            <span>{{ t.tabs.history }}</span>
            <span
              v-if="historyCount > 0"
              class="px-1.5 py-0.5 rounded-full text-[10px] font-extrabold transition-colors leading-none"
              :class="activeTab === 'history' ? 'bg-amber-100 text-amber-800 border border-amber-200' : 'bg-slate-200/80 text-slate-600'"
            >
              {{ historyCount }}
            </span>
          </button>
        </nav>
      </div>

      <!-- TAB 1: STUDIO VIEW (WORKBENCH) -->
      <div v-if="activeTab === 'studio'" class="space-y-8" style="view-transition-name: tab-content">
        <Workbench
          ref="workbenchRef"
          :initial-blueprint="loadedBlueprint"
          :active-traits-count="activeTraitsCount"
          @switch-tab="(tab: string) => (activeTab = tab as any)"
          @dna-updated="refreshProfileStats"
        />
      </div>

      <!-- TAB: PRIVATE DOMAIN HUB -->
      <div v-else-if="activeTab === 'private_domain'" style="view-transition-name: tab-content">
        <PrivateDomainHub
          ref="privateDomainRef"
          :initial-topic="loungeTransferredMomentText"
        />
      </div>

      <!-- TAB: COGNITIVE CHAT LOUNGE -->
      <div v-else-if="activeTab === 'chat_lounge'" style="view-transition-name: tab-content">
        <CognitiveChatLounge
          :initial-mode="loungeInitialMode"
          @send-to-moments="handleSendFromLoungeToMoments"
          @send-to-workbench="handleSendFromLoungeToWorkbench"
        />
      </div>

      <!-- TAB 2: COGNITIVE PROFILE DASHBOARD -->
      <div v-else-if="activeTab === 'profile'" style="view-transition-name: tab-content">
        <CognitiveProfile
          @create-from-blueprint="handleCreateFromBlueprint"
          @open-interview="handleOpenInterview"
          @switch-tab="handleSwitchTabFromProfile"
        />
      </div>

      <!-- TAB 4: MATERIAL VAULT -->
      <div v-else-if="activeTab === 'vault'" style="view-transition-name: tab-content">
        <MaterialVault @create-from-material="handleCreateFromMaterial" />
      </div>

      <!-- TAB 3: CREATION HISTORY & ARCHIVE (MODULE 1) -->
      <div v-else-if="activeTab === 'history'" style="view-transition-name: tab-content">
        <CreationHistory
          @load-draft="handleLoadDraftFromHistory"
          @distribute-draft="handleDistributeFromHistory"
          @new-creation="activeTab = 'studio'"
        />
      </div>

      <!-- Global Multi-Platform Distribute Modal (for historical creations) -->
      <MultiPlatformDistributeModal
        :show="isGlobalDistributeOpen"
        :content="distributeContent"
        :title="distributeTitle"
        @close="isGlobalDistributeOpen = false"
        @update:show="(val: boolean) => (isGlobalDistributeOpen = val)"
      />

      <!-- Feature B: BYOK Model & API Key Settings Modal -->
      <ModelSettingsModal
        :is-open="isSettingsModalOpen"
        @close="isSettingsModalOpen = false"
      />

      <!-- Daily Inspiration Briefing Modal -->
      <DailyBriefingModal
        :show="isBriefingModalOpen"
        @close="isBriefingModalOpen = false"
        @update:show="(val: boolean) => (isBriefingModalOpen = val)"
        @create-with-blueprint="handleCreateWithBriefingBlueprint"
        @create-with-topic="handleCreateWithBriefingTopic"
        @briefing-updated="refreshBriefingStats"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useI18n } from './i18n'
import Workbench from './components/Workbench.vue'
import CognitiveProfile from './components/CognitiveProfile.vue'
import CreationHistory from './components/CreationHistory.vue'
import MaterialVault from './components/MaterialVault.vue'
import PrivateDomainHub from './components/PrivateDomainHub.vue'
import CognitiveChatLounge from './components/CognitiveChatLounge.vue'
import MultiPlatformDistributeModal from './components/MultiPlatformDistributeModal.vue'
import ModelSelectorPill from './components/ModelSelectorPill.vue'
import ModelSettingsModal from './components/ModelSettingsModal.vue'
import DailyBriefingModal from './components/DailyBriefingModal.vue'
import { getLocalDrafts, setLocalDrafts, type HistoryDraftItem } from './services/historyStorage'

const isSettingsModalOpen = ref(false)
const isBriefingModalOpen = ref(false)
const briefingInfo = ref<DailyBriefingData | null>(null)

import {
  checkHealth,
  fetchCognitiveProfile,
  fetchTodayBriefing,
  API_BASE_URL,
  type BenchmarkBlueprint,
  type Material,
  type DailyBriefingData,
} from './services/api'

const { t, locale, toggleLocale } = useI18n()

const briefingButtonText = computed(() => {
  if (briefingInfo.value?.unread) {
    return t.value.briefing.unreadPill
      .replace('{trending}', String(briefingInfo.value.trending_count))
      .replace('{benchmark}', String(briefingInfo.value.benchmark_count))
  }
  return t.value.briefing.pillEmpty
})

async function refreshBriefingStats() {
  try {
    briefingInfo.value = await fetchTodayBriefing()
  } catch (e) {
    console.error('Failed to fetch briefing stats:', e)
  }
}

function handleCreateWithBriefingBlueprint(payload: { blueprint: any; material: Material; topic: string }) {
  activeTab.value = 'studio'
  nextTick(() => {
    if (workbenchRef.value) {
      workbenchRef.value.loadMaterial(
        payload.material,
        payload.topic,
        payload.blueprint,
      )
    }
  })
}

function handleCreateWithBriefingTopic(topic: string) {
  activeTab.value = 'studio'
  nextTick(() => {
    if (workbenchRef.value) {
      workbenchRef.value.setTopic(topic)
    }
  })
}

// Tab view state with URL hash and query param deep linking
const getInitialTab = (): 'studio' | 'private_domain' | 'chat_lounge' | 'vault' | 'profile' | 'history' => {
  const hash = window.location.hash.replace('#', '').toLowerCase()
  if (hash === 'profile' || hash === 'history' || hash === 'studio' || hash === 'vault' || hash === 'private_domain' || hash === 'chat_lounge') {
    return hash as any
  }
  const params = new URLSearchParams(window.location.search)
  const tabParam = params.get('tab')?.toLowerCase()
  if (tabParam === 'profile' || tabParam === 'history' || tabParam === 'studio' || tabParam === 'vault' || tabParam === 'private_domain' || tabParam === 'chat_lounge') {
    return tabParam as any
  }
  return 'studio'
}

const activeTab = ref<'studio' | 'private_domain' | 'chat_lounge' | 'vault' | 'profile' | 'history'>(getInitialTab())

const loungeInitialMode = ref<'free_talk' | 'coach_inquiry' | 'timeline_review' | 'interview'>('free_talk')

function handleOpenInterview() {
  loungeInitialMode.value = 'interview'
  activeTab.value = 'chat_lounge'
}

function handleSwitchTabFromProfile(tab: string, mode?: string) {
  if (mode && tab === 'chat_lounge') {
    loungeInitialMode.value = mode as any
  }
  activeTab.value = tab as any
}

const loungeTransferredMomentText = ref('')
const privateDomainRef = ref<any>(null)

function handleSendFromLoungeToMoments(text: string) {
  loungeTransferredMomentText.value = text
  activeTab.value = 'private_domain'
  nextTick(() => {
    if (privateDomainRef.value) {
      privateDomainRef.value.setTopic(text)
    }
  })
}

function handleSendFromLoungeToWorkbench(text: string) {
  activeTab.value = 'studio'
  nextTick(() => {
    if (workbenchRef.value) {
      workbenchRef.value.setTopic(text)
    }
  })
}

watch(activeTab, (newTab) => {
  if (window.location.hash !== `#${newTab}`) {
    window.location.hash = newTab
  }
})

// Helper: wrap tab switches in View Transition when supported
function switchTab(tab: typeof activeTab.value) {
  if ('startViewTransition' in document) {
    (document as any).startViewTransition(() => {
      activeTab.value = tab
    })
  } else {
    activeTab.value = tab
  }
}
const activeTraitsCount = ref(0)
const historyCount = ref(0)
const loadedBlueprint = ref<BenchmarkBlueprint | null>(null)
const workbenchRef = ref<any>(null)

// Historical draft distribution state
const isGlobalDistributeOpen = ref(false)
const distributeContent = ref('')
const distributeTitle = ref('')

const refreshHistoryStats = () => {
  try {
    historyCount.value = getLocalDrafts().length
  } catch {
    historyCount.value = 0
  }
}

const handleLoadDraftFromHistory = (draft: HistoryDraftItem) => {
  activeTab.value = 'studio'
  nextTick(() => {
    if (workbenchRef.value) {
      workbenchRef.value.loadDraft(draft)
    }
  })
}

const handleDistributeFromHistory = (draft: HistoryDraftItem) => {
  distributeContent.value = draft.content
  distributeTitle.value = draft.topic
  isGlobalDistributeOpen.value = true
}

const handleCreateFromMaterial = (payload: { material: Material; topic: string; blueprint?: any; context?: string }) => {
  activeTab.value = 'studio'
  nextTick(() => {
    if (workbenchRef.value) {
      workbenchRef.value.loadMaterial(
        payload.material,
        payload.topic,
        payload.blueprint,
        payload.context
      )
    }
  })
}

const handleCreateFromBlueprint = (payload: { blueprint: BenchmarkBlueprint; topic?: string; context?: string; draft?: any }) => {
  if (payload.blueprint) {
    loadedBlueprint.value = payload.blueprint
    activeTab.value = 'studio'
    nextTick(() => {
      if (workbenchRef.value) {
        workbenchRef.value.loadBlueprint(
          payload.blueprint,
          payload.draft,
          payload.topic,
          payload.context
        )
      }
    })
  }
}

// Backend Connectivity Check
const backendConnected = ref(false)
const backendStatusText = ref('Connecting to backend...')

const refreshProfileStats = async () => {
  try {
    const profile = await fetchCognitiveProfile()
    const activeOrPinned = (profile.traits || []).filter(
      (t) => t.status === 'active' || t.status === 'pinned'
    )
    activeTraitsCount.value = activeOrPinned.length
  } catch (e) {
    console.error('Failed to load profile stats:', e)
  }
}

onMounted(async () => {
  try {
    const data = await checkHealth()
    backendConnected.value = true
    backendStatusText.value = `Backend ready: ${data.message || 'Connected'}`
  } catch {
    backendConnected.value = false
    backendStatusText.value = `Backend offline (ensure backend is running on ${API_BASE_URL})`
  }
  window.addEventListener('hashchange', () => {
    const h = window.location.hash.replace('#', '').toLowerCase()
    if (h === 'studio' || h === 'vault' || h === 'profile' || h === 'history') {
      activeTab.value = h as any
    }
  })
  await refreshProfileStats()
  refreshHistoryStats()
  await refreshBriefingStats()
  // Seed demo draft if requested via ?seed=1 or if history is completely empty
  const urlParams = new URLSearchParams(window.location.search)
  if (urlParams.get('seed') === '1' || urlParams.get('tab') === 'history') {
    const existing = getLocalDrafts()
    if (existing.length === 0) {
      const demoItem: HistoryDraftItem = {
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
      }
      setLocalDrafts([demoItem])
      refreshHistoryStats()
    }
  }

  if (urlParams.get('modal') === 'distribute') {
    distributeContent.value = '真正拉开超级个体差距的，从来不是代码产出效率，而是认知杠杆的复合积累。坚持长期主义，拒绝低效内卷，在行动中穿透迷雾，直击商业本质。'
    distributeTitle.value = '独立开发者的超级个体跃迁模型'
    isGlobalDistributeOpen.value = true
  }
})
</script>
