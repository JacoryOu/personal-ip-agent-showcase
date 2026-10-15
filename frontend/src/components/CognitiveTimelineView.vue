<template>
  <div class="space-y-6">
    <!-- Top Filter Bar -->
    <div class="glass-card border border-slate-200/80 rounded-2xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4 scroll-reveal">
      <div>
        <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
          <span>⏳</span>
          <span>双轨全息时光长河 (Dual-Track Holographic Timeline)</span>
        </h3>
        <p class="text-xs text-slate-500 mt-0.5">
          轨道 A（思想演化树 V1 ➔ V2）与 轨道 B（生活踩坑故事 & Obsidian 本地日记）交织呈现
        </p>
      </div>

      <!-- Track Filters -->
      <div class="flex items-center gap-1.5 text-xs font-bold bg-slate-100 p-1 rounded-xl">
        <button
          type="button"
          @click="activeTrack = 'all'"
          class="px-3 py-1.5 rounded-lg transition cursor-pointer"
          :class="activeTrack === 'all' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'"
        >
          全轨汇聚 ({{ timelineEvents.length }})
        </button>
        <button
          type="button"
          @click="activeTrack = 'track_a'"
          class="px-3 py-1.5 rounded-lg transition cursor-pointer"
          :class="activeTrack === 'track_a' ? 'bg-purple-600 text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900'"
        >
          轨道 A: 认知演化
        </button>
        <button
          type="button"
          @click="activeTrack = 'track_b'"
          class="px-3 py-1.5 rounded-lg transition cursor-pointer"
          :class="activeTrack === 'track_b' ? 'bg-emerald-600 text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900'"
        >
          轨道 B: 经历与笔记
        </button>
      </div>
    </div>

    <!-- Obsidian Bridge Quick Banner -->
    <div class="bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-2xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs scroll-reveal">
      <div class="flex items-center gap-3">
        <span class="text-xl">💎</span>
        <div>
          <span class="font-bold text-white">Obsidian 本地双向知识库飞轮 (Phase 4)</span>
          <p class="text-slate-300 text-[11px] mt-0.5">
            严格只读模式扫描你的本地 Markdown 笔记库，增量提炼 #经历、#反思 标签自动铺设在时光长河中。
          </p>
        </div>
      </div>
      <button
        type="button"
        @click="showObsidianModal = true"
        class="px-3.5 py-1.5 rounded-xl font-bold bg-white text-slate-900 hover:bg-slate-100 shadow-2xs transition active:scale-95 cursor-pointer whitespace-nowrap"
      >
        配置挂载目录
      </button>
    </div>

    <!-- Timeline Dual Track Stream -->
    <div v-if="filteredEvents.length === 0" class="bg-white border border-slate-200/80 rounded-3xl p-16 text-center text-slate-400 space-y-2 scroll-fade">
      <div class="text-3xl">⏳</div>
      <p class="text-sm font-medium">时光长河暂无沉淀记录</p>
      <p class="text-xs text-slate-400">在对谈室倾诉或更新 Thinking DNA 后，演进轨迹将在此画卷般铺展。</p>
    </div>

    <div v-else class="relative border-l-2 border-indigo-200/80 ml-4 sm:ml-8 pl-6 sm:pl-8 space-y-8 my-6 cv-auto">
      <div
        v-for="item in filteredEvents"
        :key="item.id"
        class="relative group scroll-reveal"
      >
        <!-- Track Node Icon Anchor -->
        <div
          class="absolute -left-[35px] sm:-left-[43px] top-1.5 w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-xs shadow-md border-2 border-white ring-2"
          :class="
            item.type === 'dna_evolution'
              ? 'bg-purple-600 text-white ring-purple-200'
              : 'bg-emerald-600 text-white ring-emerald-200'
          "
        >
          <span>{{ item.type === 'dna_evolution' ? '🧬' : '📖' }}</span>
        </div>

        <!-- Event Card -->
        <div
          class="bg-white border rounded-2xl p-5 shadow-xs transition-all hover:shadow-md active:scale-[0.99]"
          :class="
            item.type === 'dna_evolution'
              ? 'border-purple-200/80 hover:border-purple-300'
              : 'border-emerald-200/80 hover:border-emerald-300'
          "
        >
          <!-- Top Row: Date & Track Tag -->
          <div class="flex items-center justify-between text-xs mb-2">
            <span class="font-mono font-bold text-slate-400">
              📅 {{ formatDate(item.occurred_at) }}
            </span>
            <span
              class="px-2 py-0.5 rounded-full text-[10px] font-extrabold border"
              :class="
                item.type === 'dna_evolution'
                  ? 'bg-purple-50 text-purple-700 border-purple-200'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-200'
              "
            >
              {{ item.type === 'dna_evolution' ? '轨道 A · 认知版本跃迁' : '轨道 B · 生活切片/笔记' }}
            </span>
          </div>

          <!-- Title -->
          <h4 class="text-sm font-black text-slate-900 leading-snug">
            {{ item.title }}
          </h4>

          <!-- Summary / Content -->
          <p v-if="item.summary" class="text-xs text-slate-600 leading-relaxed mt-2">
            {{ item.summary }}
          </p>

          <!-- Evolution Reason Box for DNA Versioning -->
          <div
            v-if="item.type === 'dna_evolution' && item.evolution_reason"
            class="mt-3 bg-purple-50/70 border border-purple-200 rounded-xl p-3 text-xs text-purple-900 space-y-1"
          >
            <div class="font-bold flex items-center gap-1">
              <span>🌱</span>
              <span>版本演进动因 (Version {{ item.version || 2 }})：</span>
            </div>
            <p class="text-[11px] leading-relaxed text-purple-800">
              {{ item.evolution_reason }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Obsidian Config Modal -->
    <div
      v-if="showObsidianModal"
      class="fixed inset-0 z-50 glass-card-dark flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h4 class="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>💎</span>
            <span>Obsidian 本地目录挂载</span>
          </h4>
          <button @click="showObsidianModal = false" class="text-slate-400 hover:text-slate-600 cursor-pointer">✕</button>
        </div>

        <div class="space-y-3 text-xs">
          <div>
            <label class="block font-bold text-slate-700 mb-1">本地 Vault 绝对路径</label>
            <input
              v-model="obsidianPath"
              type="text"
              placeholder="如：E:/MyNotes/PersonalVault"
              class="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-indigo-100 outline-none"
            />
          </div>

          <div class="bg-amber-50 border border-amber-200 rounded-xl p-3 text-[11px] text-amber-900 leading-relaxed">
            🛡️ <b>绝对物理只读承诺</b>：本引擎以只读模式访问该目录，仅提取 Markdown 标签与日期，绝不会篡改或删除您的本地文件。
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            @click="showObsidianModal = false"
            class="px-4 py-2 rounded-xl text-xs text-slate-600 hover:bg-slate-100 cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            :disabled="isScanningObsidian || !obsidianPath"
            @click="handleScanObsidian"
            class="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 cursor-pointer disabled:opacity-50"
          >
            {{ isScanningObsidian ? '扫描中...' : '测试并扫描' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  fetchTimeline,
  scanObsidianVault,
  type TimelineEventItem,
} from '../services/api'

const activeTrack = ref<'all' | 'track_a' | 'track_b'>('all')
const timelineEvents = ref<TimelineEventItem[]>([])
const showObsidianModal = ref(false)
const obsidianPath = ref('')
const isScanningObsidian = ref(false)

const filteredEvents = computed(() => {
  if (activeTrack.value === 'track_a') {
    return timelineEvents.value.filter(e => e.type === 'dna_evolution')
  }
  if (activeTrack.value === 'track_b') {
    return timelineEvents.value.filter(e => e.type === 'story')
  }
  return timelineEvents.value
})

function formatDate(iso?: string | null): string {
  if (!iso) return '岁月沉淀'
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  } catch {
    return iso
  }
}

async function loadTimeline() {
  try {
    const events = await fetchTimeline()
    if (events && events.length > 0) {
      timelineEvents.value = events
    } else {
      // Seed rich default timeline points
      timelineEvents.value = [
        {
          id: 'ev-1',
          type: 'dna_evolution',
          title: '认知迭代：从盲目清热祛湿到温阳健脾内养',
          summary: '早期盲目跟风喝红豆薏米生冷茶，导致很多体虚胃寒者脾胃更伤。经过实践反思，将认知升级为温和健脾与顺应四季节律。',
          evolution_reason: '观察到多位客户饮用生薏仁茶后腹泻便溏，深入探究李东垣《脾胃论》，修正调养底色。',
          version: 2,
          occurred_at: '2026-03-15T08:00:00Z',
        },
        {
          id: 'st-1',
          type: 'story',
          title: '初遇新会五年陈皮老白茶的味觉触动',
          summary: '在潮湿阴冷的入冬午后，第一次将五年陈老寿眉与地道新会陈皮同煮，药香与陈香交融，那一刻彻底确立了调养产品的初心。',
          story_type: 'daily_life',
          occurred_at: '2025-11-20T14:30:00Z',
        },
        {
          id: 'ev-2',
          type: 'dna_evolution',
          title: '认知确立：超级个体不贩卖焦虑，只传递确定性',
          summary: '从早期的恐吓式营销觉醒，转变为细水长流的真实生活陪伴者，打造高信任私域壁垒。',
          evolution_reason: '读者对焦虑营销逐渐疲倦，唯有真实有温度的利他内容能穿越周期。',
          version: 2,
          occurred_at: '2025-05-10T10:00:00Z',
        },
        {
          id: 'st-2',
          type: 'story',
          title: '第一次举办线下节气茶会的反思',
          summary: '原本准备了一大堆艰深的中医理论术语，发现大家最想听的反而是如何煮好一碗家常润燥汤。',
          story_type: 'failure_reflection',
          occurred_at: '2024-09-23T15:00:00Z',
        },
      ]
    }
  } catch (err) {
    console.error('Failed to fetch timeline:', err)
  }
}

async function handleScanObsidian() {
  if (!obsidianPath.value) return
  isScanningObsidian.value = true
  try {
    const res = await scanObsidianVault({
      vault_path: obsidianPath.value,
      target_tags: ['经历', '反思', '体质', '好物'],
    })
    alert(`扫描成功！共发现 ${res.total_matched || 0} 篇符合条件的笔记。`)
    showObsidianModal.value = false
    await loadTimeline()
  } catch (e: any) {
    alert(`扫描失败: ${e.message || e}`)
  } finally {
    isScanningObsidian.value = false
  }
}

onMounted(() => {
  loadTimeline()
})
</script>
