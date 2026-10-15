<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Header with 3 Mode Toggles -->
    <div class="bg-white border border-slate-200/80 rounded-3xl p-6 shadow-xs relative overflow-hidden">
      <div class="absolute -top-12 -right-12 w-64 h-64 bg-gradient-to-br from-indigo-100/40 via-sky-100/20 to-transparent rounded-full blur-2xl pointer-events-none"></div>

      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
        <div>
          <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-800 border border-indigo-200 mb-2">
            <span>💬</span>
            <span>随心倾诉 · 认知私教追问 · 时光对白</span>
          </div>
          <h2 class="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <span>认知对谈室 (Cognitive Chat Lounge)</span>
          </h2>
          <p class="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
            对内求真求准。用户随心倾诉碎片经历，启发式私教深度追问，后台实时异步萃取生活故事、思维指纹与时间图钉。
          </p>
        </div>

        <!-- Modes Segmented Control -->
        <div class="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-2xl border border-slate-200/80 flex-wrap">
          <button
            type="button"
            @click="switchMode('interview')"
            class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none flex items-center gap-1.5"
            :class="activeMode === 'interview' ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-xs' : 'text-purple-700 hover:text-purple-900 hover:bg-purple-50/50'"
          >
            <span>🎙️</span>
            <span>{{ t.ip_persona?.modeInterview || t.chatLounge?.soulInterview || '🎙️ 灵魂专访 (分身塑形)' }}</span>
          </button>
          <button
            type="button"
            @click="switchMode('free_talk')"
            class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none"
            :class="activeMode === 'free_talk' ? 'bg-white text-indigo-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
          >
            {{ t.chatLounge?.freeTalk || '🌿 自由倾诉' }}
          </button>
          <button
            type="button"
            @click="switchMode('coach_inquiry')"
            class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none"
            :class="activeMode === 'coach_inquiry' ? 'bg-white text-indigo-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
          >
            {{ t.chatLounge?.coachInquiryShort || '🎙️ 认知追问' }}
          </button>
          <button
            type="button"
            @click="switchMode('timeline_review')"
            class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none"
            :class="activeMode === 'timeline_review' ? 'bg-white text-indigo-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
          >
            {{ t.chatLounge?.timelineReviewShort || '⏳ 时光回溯' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Main Layout: 3 Columns -->
    <div class="flex flex-col lg:flex-row gap-6 items-start h-[700px]">
      <!-- LEFT SIDEBAR: History Sessions (240px) -->
      <div class="w-full lg:w-[240px] shrink-0 bg-white border border-slate-200/80 rounded-3xl shadow-xs flex flex-col h-full overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 class="text-sm font-bold text-slate-900">📜 历史对谈会话</h3>
        </div>
        <div class="p-3">
          <button
            type="button"
            @click="startNewSession"
            class="w-full py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition cursor-pointer shadow-sm"
          >
            + 新建分身对谈
          </button>
        </div>
        <div class="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
          <div
            v-for="s in sessions"
            :key="s.session_id"
            @click="switchSession(s.session_id)"
            class="p-3 rounded-2xl border cursor-pointer transition-all text-left"
            :class="currentSessionId === s.session_id ? 'border-indigo-500 bg-indigo-50/50 shadow-sm' : 'border-slate-100 hover:border-indigo-300 hover:bg-slate-50'"
          >
            <div class="flex justify-between items-start mb-1">
              <h4 class="text-xs font-bold text-slate-900 truncate pr-2 flex-1">{{ s.title || '新对话' }}</h4>
              <div class="flex items-center">
                <button @click.stop="renameSession(s.session_id, s.title)" class="text-slate-400 hover:text-indigo-500 transition-colors px-1" title="重命名">✏️</button>
                <button @click.stop="deleteSession(s.session_id)" class="text-slate-400 hover:text-red-500 transition-colors px-1" title="删除">🗑️</button>
              </div>
            </div>
            <div class="flex justify-between items-center text-[10px] text-slate-500 mt-2">
              <span class="truncate">{{ new Date(s.updated_at).toLocaleString() }}</span>
              <span class="flex items-center gap-1 bg-white px-1.5 py-0.5 rounded-md border border-slate-200">
                <span>{{ s.mode === 'free_talk' ? '🌿' : (s.mode === 'coach_inquiry' ? '🎙️' : (s.mode === 'interview' ? '✨' : '⏳')) }}</span>
                <span class="font-mono">{{ s.message_count }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- CENTER CHAT CONTAINER (flex-1) -->
      <div class="flex-1 bg-white border border-slate-200/80 rounded-3xl shadow-xs flex flex-col h-full overflow-hidden w-full lg:w-auto">
        <!-- Chat Toolbar -->
        <div class="px-5 py-3.5 border-b border-slate-100 flex items-center justify-center text-xs bg-slate-50/50">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-50 text-purple-800 border border-purple-200">
              🪞 认知镜像分身 · 已同频 · DNA v2.0
            </span>
          </div>
        </div>

        <!-- Chat Bubble Feed -->
        <div ref="chatContainerRef" class="flex-1 overflow-y-auto p-5 space-y-4">
          <!-- Empty State Greeting -->
          <div v-if="messages.length === 0" class="text-center py-16 space-y-3">
            <div class="w-16 h-16 rounded-3xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-3xl mx-auto shadow-inner">
              {{ activeMode === 'interview' ? '🎙️' : '🪞' }}
            </div>
            <h3 class="text-base font-bold text-slate-800">
              {{ activeMode === 'interview' ? '认知灵魂专访室 (Soul Interview Lounge)' : '认知镜像分身' }}
            </h3>
            <p class="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
              {{ activeMode === 'interview'
                ? '欢迎开启灵魂专访。请随心畅聊你的个人经历、初心与擅长领域。聊得差不多了，随时点击下方【一键凝练 IP 人设】，AI 将为你自动提炼专属分身！'
                : '我是你的数字孪生分身，装载着你的 Thinking DNA 与生活切片，今天想和我复盘些什么？'
              }}
            </p>
            <div class="flex flex-wrap justify-center gap-2 pt-2">
              <button
                v-for="sample in (activeMode === 'interview' ? interviewPrompts : samplePrompts)"
                :key="sample"
                @click="inputMessage = sample"
                class="px-3 py-1.5 rounded-full text-xs bg-slate-100 text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition cursor-pointer border border-slate-200"
              >
                {{ sample }}
              </button>
            </div>
          </div>

          <!-- Message Bubbles -->
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="flex flex-col space-y-1.5 chat-bubble-enter"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'"
          >
            <div class="flex items-end gap-2 max-w-[85%]">
              <!-- AI Avatar -->
              <div
                v-if="msg.role === 'assistant'"
                class="w-7 h-7 rounded-lg bg-indigo-600 text-white text-xs font-bold flex items-center justify-center shrink-0 mb-1"
              >
                TWIN
              </div>

              <!-- Bubble Box -->
              <div
                class="px-4 py-3 rounded-2xl text-xs sm:text-sm leading-relaxed shadow-2xs whitespace-pre-wrap"
                :class="
                  msg.role === 'user'
                    ? 'bg-slate-900 text-white rounded-br-xs'
                    : 'bg-violet-50 text-slate-800 border border-violet-100 rounded-bl-xs'
                "
              >
                {{ msg.content }}
              </div>
            </div>

            <!-- Action buttons for message (Only on AI messages or substantive user messages) -->
            <div
              v-if="msg.content.length > 20 && msg.role === 'user'"
              class="flex items-center gap-2 text-[11px] pt-0.5 px-1 justify-end"
            >
              <button
                type="button"
                @click="emitSendToMoments(msg.content)"
                class="text-emerald-700 hover:text-emerald-900 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 font-semibold cursor-pointer active:scale-95"
              >
                📱 转朋友圈
              </button>
              <button
                type="button"
                @click="emitSendToWorkbench(msg.content)"
                class="text-indigo-700 hover:text-indigo-900 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-200 font-semibold cursor-pointer active:scale-95"
              >
                📝 扩写长文
              </button>
            </div>
            <div
              v-else-if="msg.content.length > 20 && msg.role === 'assistant'"
              class="flex items-center gap-2 text-[11px] pt-0.5 px-1 justify-start pl-9"
            >
              <button
                type="button"
                @click="copyText(msg.content)"
                class="text-slate-500 hover:text-slate-800 cursor-pointer"
              >
                📋 复制
              </button>
            </div>
          </div>

          <!-- Loading Indicator -->
          <div v-if="isLoading" class="flex items-center gap-2 pl-9 text-xs text-slate-400">
            <span class="animate-spin">⏳</span>
            <span>认知镜像正在思考与解析...</span>
          </div>
        </div>

        <!-- Action Card: Crystallize Persona from Interview / Session -->
        <div
          v-if="activeMode === 'interview' || messages.length >= 3"
          class="px-5 py-3 bg-gradient-to-r from-purple-50 via-indigo-50 to-pink-50 border-t border-purple-100 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-2xs toast-enter"
        >
          <div class="flex items-center gap-2 text-xs text-purple-950 font-medium">
            <span class="text-base animate-pulse">✨</span>
            <span>{{ t.ip_persona?.crystallizePrompt || '✨ 聊得差不多了？【一键将本次对谈凝练为我的专属 IP 人设】' }}</span>
          </div>
          <button
            type="button"
            @click="handleCrystallizePersona"
            :disabled="isCrystallizing || messages.length === 0"
            class="px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 shadow-md shadow-indigo-500/20 active:scale-95 transition cursor-pointer flex items-center gap-1.5 shrink-0 disabled:opacity-50"
          >
            <span v-if="isCrystallizing" class="animate-spin">🪄</span>
            <span v-else>✨</span>
            <span>{{ isCrystallizing ? (t.ip_persona?.crystallizingPrompt || '正在凝练人设中...') : (t.ip_persona?.crystallizePromptBtn || '一键凝练专属 IP 人设') }}</span>
          </button>
        </div>

        <!-- Chat Input Footer -->
        <div class="p-4 border-t border-slate-100 bg-white space-y-2">
          <div class="flex items-end gap-2">
            <textarea
              v-model="inputMessage"
              @keydown.enter.prevent="handleEnter"
              rows="3"
              placeholder="在此倾诉一段经历或反思... 按 Enter 发送"
              class="flex-1 text-xs sm:text-sm px-4 py-2.5 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none resize-none"
            ></textarea>
            <button
              type="button"
              :disabled="isLoading || !inputMessage.trim()"
              @click="handleSendMessage"
              class="px-5 py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer h-[50px] flex items-center justify-center gap-1.5"
            >
              <span>发送</span>
              <span>➔</span>
            </button>
          </div>
        </div>
      </div>

      <!-- RIGHT SIDEBAR: LIVE DNA CAPSULES (280px) -->
      <div class="w-full lg:w-[280px] shrink-0 space-y-4 h-full overflow-hidden flex flex-col">
        <!-- Live Capsules Card -->
        <div class="bg-white border border-slate-200/80 rounded-3xl p-5 shadow-xs flex flex-col h-full overflow-hidden">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3 shrink-0">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>✨</span>
              <span>实时捕获胶囊</span>
            </h3>
            <span class="text-[10px] font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200">
              {{ capsules.length }} 个
            </span>
          </div>

          <div v-if="capsules.length === 0" class="py-12 text-center text-xs text-slate-400 space-y-2">
            <div class="text-2xl">🌿</div>
            <p>对谈过程中，系统将实时捕获并展现新的认知胶囊与时间图钉。</p>
          </div>

          <!-- Capsule Cards Stream -->
          <div class="flex-1 overflow-y-auto pr-1 mt-4 space-y-3 pb-4">
            <div
              v-for="(cap, i) in capsules"
              :key="i"
              class="p-3.5 rounded-2xl border transition-all text-left space-y-1.5 bg-gradient-to-br capsule-enter"
              :class="getCapsuleTheme(cap.type)"
            >
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full border" :class="getCapsuleBadge(cap.type)">
                  {{ getCapsuleTypeName(cap.type) }}
                </span>
                <span v-if="cap.occurred_at" class="text-[10px] font-mono text-slate-400">
                  📅 {{ cap.occurred_at }}
                </span>
              </div>
              <h4 class="text-xs font-bold text-slate-900">
                {{ cap.title }}
              </h4>
              <p class="text-[11px] text-slate-600 leading-relaxed">
                {{ cap.summary }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Crystallize Success Modal -->
    <div
      v-if="showCrystallizeSuccessModal && crystallizedResult"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
    >
      <div
        class="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-5 my-8 max-h-[90vh] flex flex-col relative overflow-hidden toast-enter"
      >
        <div
          class="absolute -top-12 -right-12 w-48 h-48 bg-gradient-to-br from-purple-200/50 via-indigo-200/30 to-transparent rounded-full blur-3xl pointer-events-none"
        ></div>

        <!-- Header -->
        <div class="flex items-center justify-between border-b border-slate-100 pb-3 relative z-10">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-purple-500 to-indigo-600 text-white flex items-center justify-center text-xl shadow-sm">
              🎉
            </div>
            <div>
              <h3 class="text-base sm:text-lg font-black text-slate-900 flex items-center gap-2">
                <span>{{ t.ip_persona?.crystallizeSuccessTitle || '灵魂专访人设凝练成功！' }}</span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                  Crystallized
                </span>
              </h3>
              <p class="text-xs text-slate-500 mt-0.5">
                {{ t.ip_persona?.crystallizeSuccessSubtitle || '已从本次对谈中提炼出你的专属 IP 人设档案与人生经历故事。' }}
              </p>
            </div>
          </div>
          <button
            type="button"
            @click="showCrystallizeSuccessModal = false"
            class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
          >
            ✕
          </button>
        </div>

        <!-- Crystallized Content Body -->
        <div class="space-y-4 overflow-y-auto pr-1 flex-1 relative z-10">
          <!-- Persona Card -->
          <div class="bg-gradient-to-br from-purple-50/50 via-indigo-50/30 to-white border border-purple-200/80 rounded-2xl p-5 shadow-xs space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-xl">🎭</span>
                <span class="font-black text-slate-900 text-base">{{ crystallizedResult.persona?.name }}</span>
                <span v-if="isPersonaActive" class="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-200">
                  ✅ 已激活使用
                </span>
              </div>
              <span class="text-xs text-slate-500">
                称谓：<strong class="text-slate-700 font-bold">{{ crystallizedResult.persona?.reader_salutation || '读者朋友' }}</strong>
              </span>
            </div>

            <div class="text-xs bg-white/80 border border-purple-100 p-3 rounded-xl text-slate-700 space-y-1">
              <div class="font-bold text-slate-900">🎙️ 语气风格：</div>
              <div class="text-slate-600 leading-relaxed">{{ crystallizedResult.persona?.tone_style || '真诚温暖、通俗有力' }}</div>
            </div>

            <div class="text-xs bg-white/80 border border-purple-100 p-3 rounded-xl text-slate-700 space-y-1">
              <div class="font-bold text-slate-900">🎯 目标受众：</div>
              <div class="text-slate-600 leading-relaxed">{{ crystallizedResult.persona?.target_audience || '追求个人成长与认知提升的读者群体' }}</div>
            </div>

            <div class="text-xs bg-white/80 border border-purple-100 p-3 rounded-xl text-slate-700 space-y-1">
              <div class="font-bold text-slate-900">📖 渊源故事：</div>
              <div class="text-slate-600 leading-relaxed line-clamp-4">{{ crystallizedResult.persona?.origin_story }}</div>
            </div>
          </div>

          <!-- Extracted Stories Section -->
          <div v-if="crystallizedResult.stories && crystallizedResult.stories.length > 0" class="space-y-2">
            <h4 class="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <span>📖</span>
              <span>同步萃取的经历切片故事 ({{ crystallizedResult.stories.length }} 个)</span>
            </h4>
            <div class="space-y-2">
              <div
                v-for="(st, sIdx) in crystallizedResult.stories"
                :key="sIdx"
                class="p-3 bg-white border border-slate-200 rounded-xl text-xs space-y-1 shadow-2xs"
              >
                <div class="flex items-center justify-between font-bold text-slate-900">
                  <span>{{ st.title || '对谈经历切片' }}</span>
                  <span class="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-mono">{{ st.story_type || 'daily_life' }}</span>
                </div>
                <p class="text-slate-600 line-clamp-2 leading-relaxed">{{ st.story_content }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="flex items-center justify-between border-t border-slate-100 pt-3 relative z-10">
          <div class="text-xs text-slate-500">
            已成功凝练入库
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="showCrystallizeSuccessModal = false"
              class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl transition cursor-pointer"
            >
              {{ t.ip_persona?.crystallizeCloseBtn || '继续对谈' }}
            </button>
            <button
              type="button"
              @click="handleSwitchToNewPersona"
              :disabled="isSwitchingPersona"
              class="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs rounded-xl shadow-md shadow-indigo-500/20 active:scale-95 transition cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              <span>{{ isPersonaActive ? '✅ 人设已生效' : (t.ip_persona?.crystallizeSwitchBtn || '✨ 一键切换/激活新人设') }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useI18n } from '../i18n'
import {
  sendLoungeMessage,
  fetchLoungeSessions,
  deleteLoungeSession,
  renameLoungeSession,
  crystallizePersonaFromSession,
  fetchPersonas,
  activatePersona,
  type DNACapsule,
  type CrystallizePersonaResponse,
} from '../services/api'
import { API_BASE_URL, apiFetch } from '../services/api' // needed for history

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    initialMode?: 'free_talk' | 'coach_inquiry' | 'timeline_review' | 'interview'
  }>(),
  {
    initialMode: 'free_talk',
  }
)

const emit = defineEmits<{
  (e: 'send-to-moments', text: string): void
  (e: 'send-to-workbench', text: string): void
  (e: 'persona-crystallized', result: CrystallizePersonaResponse): void
}>()

const activeMode = ref<'free_talk' | 'coach_inquiry' | 'timeline_review' | 'interview'>(props.initialMode || 'free_talk')

watch(
  () => props.initialMode,
  (newMode) => {
    if (newMode) {
      activeMode.value = newMode
    }
  },
  { immediate: true }
)
const sessionId = ref<string>('')
const currentSessionId = ref<string>('')
const inputMessage = ref('')
const isLoading = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string; ts?: string }>>([])
const capsules = ref<DNACapsule[]>([])
const sessions = ref<any[]>([])
const chatContainerRef = ref<HTMLDivElement | null>(null)

const samplePrompts = [
  '2023年冬我初入养生行业，当时以为喝凉茶能解决所有湿气，结果适得其反。',
  '最近发现很多职场女性总在下午两点犯困，我测试了老白茶加陈皮的效果非常惊艳。',
  '两年前我盲目追求生酮饮食，现在越来越体会到顺应节气饮食的重要性。',
]

const interviewPrompts = [
  '我想聊聊从大厂裸辞做自由职业的初心与最大困难...',
  '聊聊我做健康养生这几年，服务过印象最深的一位客户案例...',
  '我擅长把复杂晦涩的技术讲得通俗易懂，想做一个技术布道者IP...',
]

const isCrystallizing = ref(false)
const showCrystallizeSuccessModal = ref(false)
const crystallizedResult = ref<CrystallizePersonaResponse | null>(null)
const isPersonaActive = ref(false)
const isSwitchingPersona = ref(false)

async function handleCrystallizePersona() {
  const targetSessionId = sessionId.value || currentSessionId.value
  if (!targetSessionId) {
    alert('暂无有效对谈记录')
    return
  }

  isCrystallizing.value = true
  try {
    const res = await crystallizePersonaFromSession(targetSessionId)
    crystallizedResult.value = res
    isPersonaActive.value = Boolean(res.persona?.is_active)
    showCrystallizeSuccessModal.value = true
    emit('persona-crystallized', res)
  } catch (err: any) {
    console.error('Crystallize persona failed:', err)
    alert(`凝练人设失败: ${err.message || err}`)
  } finally {
    isCrystallizing.value = false
  }
}

async function handleSwitchToNewPersona() {
  const pId = crystallizedResult.value?.persona?.id
  if (!pId) return
  isSwitchingPersona.value = true
  try {
    try {
      const existing = await fetchPersonas()
      for (const p of existing) {
        if (p.is_active && p.id !== pId) {
          await activatePersona(p.id, false)
        }
      }
    } catch (e) {
      console.warn('Deactivating others failed:', e)
    }
    await activatePersona(pId, true)
    isPersonaActive.value = true
    alert(`已成功切换并激活人设「${crystallizedResult.value?.persona?.name}」！`)
  } catch (err: any) {
    console.error('Activate persona failed:', err)
    alert(`激活人设失败: ${err.message || err}`)
  } finally {
    isSwitchingPersona.value = false
  }
}

async function loadSessions() {
  try {
    sessions.value = await fetchLoungeSessions()
  } catch (err) {
    console.error(err)
  }
}

async function switchSession(id: string) {
  currentSessionId.value = id
  sessionId.value = id
  messages.value = []
  capsules.value = []
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/chat/lounge/history?session_id=${id}`)
    const data = await res.json()
    if (res.ok) {
      messages.value = data.messages
    }
  } catch (err) {
    console.error(err)
  }
}

async function deleteSession(id: string) {
  if (!confirm('确定删除该会话吗？')) return
  await deleteLoungeSession(id)
  if (currentSessionId.value === id) {
    startNewSession()
  }
  await loadSessions()
}

async function renameSession(id: string, currentTitle: string) {
  const newTitle = prompt('请输入新名称：', currentTitle)
  if (newTitle && newTitle.trim() !== '' && newTitle !== currentTitle) {
    await renameLoungeSession(id, newTitle.trim())
    await loadSessions()
  }
}

function switchMode(mode: 'free_talk' | 'coach_inquiry' | 'timeline_review' | 'interview') {
  activeMode.value = mode
}

function startNewSession() {
  sessionId.value = 'session_' + Math.random().toString(36).substring(2, 9)
  currentSessionId.value = sessionId.value
  messages.value = []
  capsules.value = []
}

async function handleSendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isLoading.value) return

  inputMessage.value = ''
  messages.value.push({ role: 'user', content: text, ts: new Date().toISOString() })
  isLoading.value = true
  await scrollToBottom()

  try {
    const res = await sendLoungeMessage({
      message: text,
      mode: activeMode.value,
      session_id: sessionId.value || undefined,
    })

    if (!sessionId.value) {
      sessionId.value = res.session_id
    }

    messages.value.push({
      role: 'assistant',
      content: res.reply,
      ts: new Date().toISOString(),
    })

    if (res.capsules && res.capsules.length > 0) {
      capsules.value.unshift(...res.capsules)
    }
    await loadSessions()
  } catch (err: any) {
    messages.value.push({
      role: 'assistant',
      content: `抱歉，对谈服务响应异常：${err.message || err}`,
    })
  } finally {
    isLoading.value = false
    await scrollToBottom()
  }
}

function handleEnter(e: KeyboardEvent) {
  if (!e.shiftKey) {
    handleSendMessage()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
  }
}

function emitSendToMoments(text: string) {
  emit('send-to-moments', text)
}

function emitSendToWorkbench(text: string) {
  emit('send-to-workbench', text)
}

function copyText(text: string) {
  navigator.clipboard.writeText(text)
  alert('已复制到剪贴板！')
}

function getCapsuleTypeName(type: string): string {
  switch (type) {
    case 'story':
      return '生活切片 (Story)'
    case 'dna':
      return 'Thinking DNA 观点'
    case 'timeline_pin':
      return '时光图钉 (Pin)'
    case 'evolution':
      return '认知版本演化'
    default:
      return '全息胶囊'
  }
}

function getCapsuleTheme(type: string): string {
  switch (type) {
    case 'story':
      return 'from-emerald-50/60 to-white border-emerald-200/80'
    case 'dna':
      return 'from-purple-50/60 to-white border-purple-200/80'
    case 'timeline_pin':
      return 'from-amber-50/60 to-white border-amber-200/80'
    case 'evolution':
      return 'from-indigo-50/60 to-white border-indigo-200/80'
    default:
      return 'from-slate-50 to-white border-slate-200'
  }
}

function getCapsuleBadge(type: string): string {
  switch (type) {
    case 'story':
      return 'bg-emerald-100 text-emerald-800 border-emerald-300'
    case 'dna':
      return 'bg-purple-100 text-purple-800 border-purple-300'
    case 'timeline_pin':
      return 'bg-amber-100 text-amber-800 border-amber-300'
    case 'evolution':
      return 'bg-indigo-100 text-indigo-800 border-indigo-300'
    default:
      return 'bg-slate-100 text-slate-800 border-slate-300'
  }
}

onMounted(async () => {
  await loadSessions()
  if (props.initialMode === 'interview') {
    startNewSession()
  } else if (sessions.value && sessions.value.length > 0) {
    await switchSession(sessions.value[0].session_id)
  } else {
    startNewSession()
  }
})
</script>
