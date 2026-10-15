<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 overflow-y-auto glass-card-dark flex items-center justify-center p-3 sm:p-4"
    @click.self="handleClose"
  >
    <div
      class="bg-white rounded-3xl shadow-2xl border border-slate-200/90 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden transform transition-all relative toast-enter"
    >
      <!-- Modal Header -->
      <div class="px-6 py-5 bg-gradient-to-r from-blue-50/80 via-indigo-50/60 to-purple-50/80 border-b border-slate-200/80 flex items-center justify-between gap-4 relative overflow-hidden">
        <!-- Ambient light sheen -->
        <div class="absolute -right-12 -top-12 w-48 h-48 bg-gradient-to-br from-indigo-200/30 to-transparent rounded-full blur-2xl pointer-events-none"></div>

        <div class="flex items-center gap-3 relative z-10">
          <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-600 via-indigo-600 to-indigo-700 text-white flex items-center justify-center text-xl shadow-md shadow-blue-500/25">
            📬
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-lg font-black text-slate-900 tracking-tight">
                {{ t.briefing.title }}
              </h3>
              <span
                v-if="briefingData?.date"
                class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-white/95 text-indigo-700 border border-indigo-200/80 shadow-2xs"
              >
                {{ briefingData.date }}
              </span>
              <span
                v-if="briefingData?.unread"
                class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-500 text-white shadow-xs shadow-rose-500/30 animate-pulse"
              >
                NEW
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-0.5 max-w-xl line-clamp-1 leading-relaxed">
              {{ t.briefing.subtitle }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 relative z-10">
          <!-- Manual Trigger Button -->
          <button
            type="button"
            @click="handleManualTrigger"
            :disabled="isTriggering"
            class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-blue-700 bg-white/90 hover:bg-white border border-blue-200/80 shadow-2xs hover:shadow-xs transition active:scale-95 cursor-pointer disabled:opacity-50"
            title="手动触发后台双轮巡检"
          >
            <span :class="{ 'animate-spin': isTriggering }">⚡</span>
            <span>{{ isTriggering ? t.briefing.triggering : t.briefing.triggerBtn }}</span>
          </button>

          <!-- Close Button -->
          <button
            type="button"
            @click="handleClose"
            class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100/80 transition cursor-pointer"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="px-6 border-b border-slate-200/80 bg-slate-50/60 flex items-center justify-between">
        <div class="flex items-center gap-2 pt-2.5">
          <button
            type="button"
            @click="activeSection = 'trending'"
            class="px-4 py-2 text-xs font-bold rounded-t-xl transition-all border-b-2 cursor-pointer flex items-center gap-1.5"
            :class="
              activeSection === 'trending'
                ? 'border-amber-600 text-amber-700 bg-white shadow-2xs'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
          >
            <span>🔥 {{ t.briefing.tabTrending }}</span>
            <span
              class="px-1.5 py-0.2 rounded-full text-[10px] font-bold"
              :class="activeSection === 'trending' ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-600'"
            >
              {{ briefingData?.trending_count || 0 }}
            </span>
          </button>

          <button
            type="button"
            @click="activeSection = 'benchmark'"
            class="px-4 py-2 text-xs font-bold rounded-t-xl transition-all border-b-2 cursor-pointer flex items-center gap-1.5"
            :class="
              activeSection === 'benchmark'
                ? 'border-blue-600 text-blue-700 bg-white shadow-2xs'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
          >
            <span>🎯 {{ t.briefing.tabBenchmark }}</span>
            <span
              class="px-1.5 py-0.2 rounded-full text-[10px] font-bold"
              :class="activeSection === 'benchmark' ? 'bg-blue-100 text-blue-800' : 'bg-slate-200 text-slate-600'"
            >
              {{ briefingData?.benchmark_count || 0 }}
            </span>
          </button>

          <button
            type="button"
            @click="activeSection = 'settings'"
            class="px-4 py-2 text-xs font-bold rounded-t-xl transition-all border-b-2 cursor-pointer flex items-center gap-1.5"
            :class="
              activeSection === 'settings'
                ? 'border-purple-600 text-purple-700 bg-white shadow-2xs'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
          >
            <span>⚙️ {{ t.briefing.tabSettings }}</span>
          </button>
        </div>

        <div v-if="statusData?.last_run_time" class="hidden sm:block text-[11px] text-slate-400 font-medium">
          {{ t.briefing.lastRun }}: {{ formatTime(statusData.last_run_time) }}
        </div>
      </div>

      <!-- Modal Body Content with Sleek Scrollbar -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6 [scrollbar-width:thin] [scrollbar-color:#cbd5e1_transparent]">
        <!-- Toast Notification -->
        <div
          v-if="toastMessage"
          class="p-3.5 rounded-2xl bg-emerald-50/90 border border-emerald-200/90 text-emerald-800 text-xs font-semibold flex items-center justify-between shadow-2xs animate-in fade-in"
        >
          <span class="flex items-center gap-1.5">✓ {{ toastMessage }}</span>
          <button type="button" @click="toastMessage = ''" class="text-emerald-600 hover:text-emerald-900 cursor-pointer">✕</button>
        </div>

        <!-- TAB 1: TRENDING TOPICS (WHEEL 1) -->
        <div v-if="activeSection === 'trending'" class="space-y-4">
          <div
            v-if="!briefingData?.trending_topics || briefingData.trending_topics.length === 0"
            class="p-12 text-center text-slate-400 bg-slate-50/80 rounded-3xl border border-dashed border-slate-200"
          >
            <span class="text-4xl block mb-2">📡</span>
            <p class="text-sm font-bold text-slate-700">{{ t.briefing.noItemsToday }}</p>
            <p class="text-xs text-slate-400 mt-1">{{ t.briefing.emptyHint }}</p>
          </div>

          <div
            v-for="(item, idx) in briefingData?.trending_topics || []"
            :key="item.id || idx"
            class="p-5 rounded-3xl bg-white border border-slate-200/80 shadow-xs hover:border-amber-300/90 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 group"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-2 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <!-- Platform Badge -->
                  <span
                    class="px-2.5 py-0.5 rounded-lg text-[11px] font-bold shadow-2xs border"
                    :class="getPlatformBadgeClass(item.source_platform)"
                  >
                    {{ formatPlatformName(item.source_platform) }}
                  </span>

                  <!-- Hot Score Flame -->
                  <span
                    v-if="item.meta_info?.hot_value || item.meta_info?.hot_score"
                    class="px-2.5 py-0.5 rounded-lg text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200/80 shadow-2xs"
                  >
                    🔥 {{ formatHotValue(item.meta_info?.hot_value || item.meta_info?.hot_score) }}
                  </span>

                  <!-- Relevance Score -->
                  <span
                    v-if="item.meta_info?.score"
                    class="px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs"
                  >
                    🎯 {{ Math.round(Number(item.meta_info.score) * 100) }}% {{ t.briefing.relevanceScore }}
                  </span>

                  <span class="text-[11px] text-slate-400 font-medium">
                    👤 {{ item.source_author || '全网热榜' }}
                  </span>
                </div>

                <h4 class="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition leading-snug">
                  <a
                    v-if="item.source_url"
                    :href="item.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="hover:underline flex items-center gap-1.5"
                  >
                    <span>{{ item.title }}</span>
                    <span class="text-slate-400 text-xs">↗</span>
                  </a>
                  <span v-else>{{ item.title }}</span>
                </h4>

                <p class="text-xs text-slate-600 line-clamp-2 leading-relaxed whitespace-pre-wrap">
                  {{ item.cleaned_content || item.raw_content || item.title }}
                </p>

                <!-- Tags -->
                <div class="flex flex-wrap items-center gap-1.5 pt-1">
                  <span
                    v-for="tag in item.tags || []"
                    :key="tag"
                    class="px-2 py-0.5 rounded-md bg-slate-100/80 text-slate-600 text-[10px] font-medium border border-slate-200/60"
                  >
                    #{{ tag }}
                  </span>
                </div>
              </div>

              <!-- Action Button -->
              <div class="flex flex-col gap-2 shrink-0">
                <button
                  type="button"
                  @click="handleCreateWithTopic(item)"
                  class="px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 via-indigo-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 shadow-sm shadow-indigo-500/20 active:scale-95 transition-all cursor-pointer whitespace-nowrap"
                >
                  {{ t.briefing.createWithTopic }}
                </button>
                <span class="text-center text-[10px] font-semibold text-emerald-700 bg-emerald-50/90 px-2 py-0.5 rounded-lg border border-emerald-200/80 shadow-2xs">
                  ✓ 已入素材库
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 2: BENCHMARK VIRAL BLUEPRINTS (WHEEL 2) -->
        <div v-else-if="activeSection === 'benchmark'" class="space-y-4">
          <div
            v-if="!briefingData?.benchmark_blueprints || briefingData.benchmark_blueprints.length === 0"
            class="p-12 text-center text-slate-400 bg-slate-50/80 rounded-3xl border border-dashed border-slate-200"
          >
            <span class="text-4xl block mb-2">🦴</span>
            <p class="text-sm font-bold text-slate-700">{{ t.briefing.noItemsToday }}</p>
            <p class="text-xs text-slate-400 mt-1">{{ t.briefing.emptyHint }}</p>
          </div>

          <div
            v-for="(item, idx) in briefingData?.benchmark_blueprints || []"
            :key="item.id || idx"
            class="p-5 sm:p-6 rounded-3xl bg-white border border-slate-200/80 shadow-xs hover:border-indigo-300/90 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 group space-y-3.5"
          >
            <!-- Header Info -->
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span
                    class="px-2.5 py-0.5 rounded-lg text-[11px] font-bold shadow-2xs border"
                    :class="getPlatformBadgeClass(item.source_platform)"
                  >
                    {{ formatPlatformName(item.source_platform) }}
                  </span>
                  <span class="text-xs font-bold text-slate-800">
                    {{ item.source_author || '对标创作者' }}
                  </span>
                  <span
                    v-if="item.meta_info?.likes"
                    class="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs"
                  >
                    ❤️ {{ formatHotValue(item.meta_info.likes) }}
                  </span>
                  <span
                    v-if="item.meta_info?.shares"
                    class="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200/80 shadow-2xs"
                  >
                    🔁 {{ formatHotValue(item.meta_info.shares) }}
                  </span>
                </div>

                <h4 class="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-blue-600 transition leading-snug">
                  <a
                    v-if="item.source_url"
                    :href="item.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="hover:underline flex items-center gap-1.5"
                  >
                    <span>{{ item.title }}</span>
                    <span class="text-slate-400 text-xs">↗</span>
                  </a>
                  <span v-else>{{ item.title }}</span>
                </h4>
              </div>

              <!-- Primary Action -->
              <button
                type="button"
                @click="handleCreateWithBlueprint(item)"
                class="px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md shadow-indigo-500/20 active:scale-95 transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5"
              >
                <span>🦴</span>
                <span>{{ t.briefing.createWithBlueprint }}</span>
              </button>
            </div>

            <!-- Structural Bones / Blueprint Card -->
            <div
              v-if="item.blueprint_data"
              class="p-4 rounded-2xl bg-gradient-to-br from-amber-50/80 via-orange-50/40 to-amber-50/60 border border-amber-200/90 shadow-2xs space-y-2.5 text-xs"
            >
              <div class="flex items-start gap-1.5 text-[11px] leading-relaxed">
                <span class="font-bold text-amber-900 bg-amber-100/90 border border-amber-200/60 px-1.5 py-0.5 rounded-md shrink-0 shadow-2xs">🪝 {{ t.briefing.openingHook }}</span>
                <span class="text-slate-800 font-medium pt-0.5">
                  {{ item.blueprint_data.opening_hook || item.blueprint_data.hook_style || '开门见山抛出刺痛痛点' }}
                </span>
              </div>

              <div v-if="item.blueprint_data.emotional_arc" class="flex items-start gap-1.5 text-[11px] leading-relaxed">
                <span class="font-bold text-indigo-900 bg-indigo-100/90 border border-indigo-200/60 px-1.5 py-0.5 rounded-md shrink-0 shadow-2xs">📈 {{ t.briefing.emotionalArc }}</span>
                <span class="text-slate-800 font-medium pt-0.5 bg-indigo-50/80 px-2 py-0.5 rounded-md">
                  {{ item.blueprint_data.emotional_arc }}
                </span>
              </div>

              <div
                v-if="item.blueprint_data.structural_stages || item.blueprint_data.key_stages"
                class="space-y-1.5 pt-0.5"
              >
                <span class="font-bold text-amber-900 block">🧱 {{ t.briefing.structuralStages }}:</span>
                <div class="flex flex-wrap items-center gap-1.5">
                  <span
                    v-for="(stg, sIdx) in (item.blueprint_data.structural_stages || item.blueprint_data.key_stages)"
                    :key="sIdx"
                    class="px-2 py-0.5 rounded-lg bg-white/95 border border-amber-200/80 text-amber-950 text-[10px] font-semibold shadow-2xs"
                  >
                    {{ Number(sIdx) + 1 }}. {{ stg }}
                  </span>
                </div>
              </div>

              <div v-if="item.blueprint_data.pacing" class="text-[11px] text-amber-800 flex items-center gap-1.5">
                <span class="font-semibold">{{ t.briefing.pacing }}:</span>
                <span class="font-medium text-slate-700">{{ item.blueprint_data.pacing }}</span>
              </div>
            </div>

            <!-- Original Preview snippet -->
            <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed">
              {{ item.cleaned_content || item.raw_content }}
            </p>
          </div>
        </div>

        <!-- TAB 3: SCHEDULER SETTINGS & POLICIES -->
        <div v-else-if="activeSection === 'settings'" class="space-y-6">
          <div class="p-5 rounded-3xl bg-slate-50/80 border border-slate-200/80 space-y-4 shadow-2xs">
            <div class="flex items-center justify-between">
              <div>
                <h4 class="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  {{ t.briefing.statusRunning }}
                </h4>
                <p class="text-xs text-slate-500 mt-0.5">
                  {{ t.briefing.nextRun }}: {{ formatTime(statusData?.next_run_time) || '未安排' }}
                </p>
              </div>

              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  v-model="editSettings.enabled"
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-slate-300 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 shadow-2xs"></div>
              </label>
            </div>

            <!-- Execution Message Pill if exists -->
            <div
              v-if="statusData?.last_execution_summary?.message"
              class="p-3 rounded-2xl bg-white border border-slate-200/80 text-xs text-slate-700 flex items-center gap-2 shadow-2xs"
            >
              <span>ℹ️</span>
              <span>{{ statusData.last_execution_summary.message }}</span>
            </div>
          </div>

          <form @submit.prevent="handleSaveSettings" class="space-y-4 text-xs">
            <!-- Wheel Toggles -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <label class="flex items-center gap-3 p-3.5 rounded-2xl border border-slate-200/80 bg-white cursor-pointer hover:bg-slate-50/80 transition shadow-2xs">
                <input type="checkbox" v-model="editSettings.wheel1_enabled" class="rounded text-blue-600 w-4 h-4" />
                <span class="font-semibold text-slate-800">{{ t.briefing.wheel1Label }}</span>
              </label>

              <label class="flex items-center gap-3 p-3.5 rounded-2xl border border-slate-200/80 bg-white cursor-pointer hover:bg-slate-50/80 transition shadow-2xs">
                <input type="checkbox" v-model="editSettings.wheel2_enabled" class="rounded text-blue-600 w-4 h-4" />
                <span class="font-semibold text-slate-800">{{ t.briefing.wheel2Label }}</span>
              </label>
            </div>

            <!-- Interval & Time -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="font-bold text-slate-700 block">{{ t.briefing.intervalHours }}</label>
                <input
                  type="number"
                  min="1"
                  max="48"
                  v-model.number="editSettings.interval_hours"
                  class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200/90 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium shadow-2xs"
                />
              </div>

              <div class="space-y-1.5">
                <label class="font-bold text-slate-700 block">{{ t.briefing.dailyTime }}</label>
                <input
                  type="text"
                  placeholder="08:30"
                  v-model="editSettings.daily_briefing_time"
                  class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200/90 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium shadow-2xs"
                />
              </div>
            </div>

            <!-- Viral Threshold -->
            <div class="space-y-1.5">
              <label class="font-bold text-slate-700 block">{{ t.briefing.viralThreshold }}</label>
              <input
                type="number"
                min="0"
                step="500"
                v-model.number="editSettings.viral_threshold_likes"
                class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200/90 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium shadow-2xs"
              />
            </div>

            <!-- Interest Tags -->
            <div class="space-y-1.5">
              <label class="font-bold text-slate-700 block">{{ t.briefing.interestTags }}</label>
              <input
                type="text"
                v-model="interestTagsInput"
                placeholder="AI, 商业, 独立开发, 超级个体, 效率, 技术变现"
                class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200/90 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium shadow-2xs"
              />
              <p class="text-[11px] text-slate-400 mt-0.5">以中英文逗号隔开不同关注领域标签</p>
            </div>

            <div class="pt-2 flex justify-end">
              <button
                type="submit"
                :disabled="isSavingSettings"
                class="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 shadow-sm transition active:scale-95 cursor-pointer disabled:opacity-50"
              >
                {{ isSavingSettings ? '正在保存...' : t.briefing.saveSettingsBtn }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-6 py-4 bg-slate-50/90 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
        <div class="text-xs text-slate-500 font-medium flex items-center gap-1.5">
          <span>📦</span>
          <span>共收录 {{ briefingData?.total_items || 0 }} 条高价值巡检素材</span>
        </div>

        <div class="flex items-center gap-2.5">
          <!-- Batch Confirm Keep in Vault -->
          <button
            type="button"
            @click="handleBatchConfirmVault"
            class="px-4 py-2 rounded-xl text-xs font-bold text-slate-700 bg-white hover:bg-slate-100 border border-slate-200/90 shadow-2xs transition active:scale-95 cursor-pointer"
          >
            {{ t.briefing.batchSaveVault }}
          </button>

          <!-- Mark Read & Close -->
          <button
            type="button"
            @click="handleMarkReadAndClose"
            class="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 shadow-md transition active:scale-95 cursor-pointer"
          >
            {{ t.briefing.markAllRead }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from '../i18n'
import {
  fetchTodayBriefing,
  fetchSchedulerStatus,
  triggerInspection,
  updateSchedulerSettings,
  markBriefingAsRead,
  confirmBriefingIntoVault,
  type DailyBriefingData,
  type SchedulerStatus,
  type SchedulerSettings,
  type Material,
} from '../services/api'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:show', val: boolean): void
  (e: 'create-with-blueprint', payload: { blueprint: any; material: Material; topic: string }): void
  (e: 'create-with-topic', topic: string): void
  (e: 'briefing-updated'): void
}>()

const activeSection = ref<'trending' | 'benchmark' | 'settings'>('trending')
const isTriggering = ref(false)
const isSavingSettings = ref(false)
const toastMessage = ref('')

const briefingData = ref<DailyBriefingData | null>(null)
const statusData = ref<SchedulerStatus | null>(null)

const editSettings = ref<SchedulerSettings>({
  enabled: true,
  interval_hours: 6,
  daily_briefing_time: '08:30',
  wheel1_enabled: true,
  wheel2_enabled: true,
  interest_tags: ['AI', '商业', '独立开发', '超级个体', '效率'],
  viral_threshold_likes: 3000,
  max_trending_per_run: 10,
  max_posts_per_account: 5,
  notify_unread: true,
})

const interestTagsInput = ref('AI, 商业, 独立开发, 超级个体, 效率')

async function loadData() {
  try {
    const [bData, sData] = await Promise.all([
      fetchTodayBriefing(),
      fetchSchedulerStatus(),
    ])
    briefingData.value = bData
    statusData.value = sData
    if (sData.settings) {
      editSettings.value = { ...sData.settings }
      interestTagsInput.value = (sData.settings.interest_tags || []).join(', ')
    }
  } catch (e) {
    console.error('Failed to load briefing data:', e)
  }
}

watch(
  () => props.show,
  (val) => {
    if (val) {
      loadData()
    }
  },
  { immediate: true }
)

function handleClose() {
  emit('update:show', false)
  emit('close')
}

async function handleManualTrigger() {
  if (isTriggering.value) return
  isTriggering.value = true
  try {
    const res = await triggerInspection()
    toastMessage.value = res.message || t.value.briefing.triggerSuccessToast
    await loadData()
    emit('briefing-updated')
  } catch (e: any) {
    toastMessage.value = `巡检失败: ${e.message || '未知错误'}`
  } finally {
    isTriggering.value = false
  }
}

async function handleSaveSettings() {
  isSavingSettings.value = true
  try {
    const tags = interestTagsInput.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)

    const updated = await updateSchedulerSettings({
      ...editSettings.value,
      interest_tags: tags,
    })
    editSettings.value = { ...updated }
    toastMessage.value = t.value.briefing.settingsSavedToast
    statusData.value = await fetchSchedulerStatus()
  } catch (e: any) {
    toastMessage.value = `保存失败: ${e.message || '未知错误'}`
  } finally {
    isSavingSettings.value = false
  }
}

async function handleMarkReadAndClose() {
  try {
    await markBriefingAsRead()
    if (briefingData.value) {
      briefingData.value.unread = false
    }
    emit('briefing-updated')
  } catch (e) {
    console.error('Failed to mark read:', e)
  }
  handleClose()
}

async function handleBatchConfirmVault() {
  try {
    const res = await confirmBriefingIntoVault()
    toastMessage.value = res.message || t.value.briefing.savedToVaultToast
    if (briefingData.value) {
      briefingData.value.unread = false
    }
    emit('briefing-updated')
  } catch (e: any) {
    toastMessage.value = `确认入库失败: ${e.message || '未知错误'}`
  }
}

function handleCreateWithTopic(item: Material) {
  emit('create-with-topic', item.title)
  handleClose()
}

function handleCreateWithBlueprint(item: Material) {
  emit('create-with-blueprint', {
    blueprint: {
      id: item.id,
      title: item.title,
      ...(item.blueprint_data || {}),
    },
    material: item,
    topic: item.title,
  })
  handleClose()
}

function formatHotValue(num?: number): string {
  if (!num) return '0'
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}w`
  }
  return String(num)
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

function formatPlatformName(plat?: string): string {
  switch ((plat || '').toLowerCase()) {
    case 'wechat':
      return '🟢 微信'
    case 'xhs':
    case 'xiaohongshu':
      return '📕 小红书'
    case 'zhihu':
      return '🔵 知乎'
    case 'weibo':
      return '🟡 微博'
    case '36kr':
      return '⚡ 36氪'
    default:
      return plat || 'web'
  }
}

function getPlatformBadgeClass(plat?: string): string {
  switch ((plat || '').toLowerCase()) {
    case 'wechat':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200/90'
    case 'xhs':
    case 'xiaohongshu':
      return 'bg-rose-50 text-rose-700 border-rose-200/90'
    case 'zhihu':
      return 'bg-blue-50 text-blue-700 border-blue-200/90'
    case 'weibo':
      return 'bg-amber-50 text-amber-700 border-amber-200/90'
    case '36kr':
      return 'bg-cyan-50 text-cyan-700 border-cyan-200/90'
    case 'douyin':
      return 'bg-slate-900 text-white border-slate-800'
    default:
      return 'bg-slate-50 text-slate-700 border-slate-200/90'
  }
}
</script>
