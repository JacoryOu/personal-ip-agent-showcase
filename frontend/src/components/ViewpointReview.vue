<template>
  <div v-if="viewpoints && viewpoints.length > 0" class="glass-card rounded-2xl border border-indigo-200/70 p-5 shadow-sm space-y-4 scroll-reveal">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-2">
      <div class="flex items-center space-x-2">
        <span class="text-xl">🎯</span>
        <h3 class="text-base font-bold text-slate-900">{{ t.viewpoints.title }}</h3>
        <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 border border-indigo-200">
          {{ t.viewpoints.badge }}
        </span>
      </div>

      <div class="flex items-center space-x-3 text-xs">
        <!-- Contrarian Stance Counter Badge -->
        <span
          v-if="activeContrarianCount > 0"
          class="inline-flex items-center px-2 py-0.5 rounded-full font-bold bg-purple-100 text-purple-700 border border-purple-200 animate-pulse"
        >
          ⚡ {{ t.viewpoints.activeStance.replace('{count}', String(activeContrarianCount)) }}
        </span>
        <span v-else class="text-slate-500">
          ✓ {{ t.viewpoints.allAgreed }}
        </span>

        <!-- Collapse / Expand Toggle -->
        <button
          type="button"
          @click="isCollapsed = !isCollapsed"
          class="text-indigo-600 hover:text-indigo-800 font-medium transition-colors cursor-pointer"
        >
          {{ isCollapsed ? t.viewpoints.expand : t.viewpoints.collapse }}
        </button>
      </div>
    </div>

    <p v-if="!isCollapsed" class="text-xs text-slate-600 leading-relaxed">
      {{ t.viewpoints.subtitle }}
    </p>

    <!-- Viewpoint Cards List -->
    <div v-if="!isCollapsed" class="space-y-3 pt-1">
      <div
        v-for="(vp, idx) in viewpoints"
        :key="vp.id || idx"
        class="p-4 rounded-xl bg-white/95 border transition-all duration-200 shadow-sm scroll-reveal"
        :class="getCardBorderClass(vp.id)"
      >
        <!-- Claim & Section Header -->
        <div class="flex items-start justify-between gap-3 mb-2.5">
          <div class="space-y-1">
            <span
              v-if="vp.section_title"
              class="inline-block px-2 py-0.5 text-[11px] font-semibold rounded bg-slate-100 text-slate-600 mr-2"
            >
              {{ vp.section_title }}
            </span>
            <span class="text-xs font-bold text-slate-400">{{ t.viewpoints.claimPrefix }} {{ idx + 1 }}</span>
            <div class="text-sm font-semibold text-slate-800 leading-snug">
              “{{ vp.claim }}”
            </div>
          </div>
        </div>

        <!-- Stance Options Buttons -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
          <button
            v-for="opt in vp.options"
            :key="opt.key"
            type="button"
            @click="selectOption(vp, opt.key, opt.text)"
            class="text-left p-2.5 rounded-lg border text-xs transition-all relative flex flex-col justify-between"
            :class="getOptionButtonClass(vp.id, opt.key)"
          >
            <div class="flex items-center justify-between mb-1">
              <span class="font-bold flex items-center space-x-1">
                <span v-if="opt.key === 'agree'">✅</span>
                <span v-else-if="opt.key === 'counter'">🔄</span>
                <span v-else>💡</span>
                <span>{{ opt.label }}</span>
              </span>
              <span
                v-if="isOptionSelected(vp.id, opt.key)"
                class="w-2 h-2 rounded-full bg-indigo-600"
              ></span>
            </div>
            <div class="text-[11px] text-slate-600 leading-snug line-clamp-2">
              {{ opt.text }}
            </div>
          </button>
        </div>

        <!-- Custom Note Toggle & Input -->
        <div class="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2">
          <button
            type="button"
            @click="toggleCustomNote(vp.id)"
            class="text-[11px] text-slate-500 hover:text-indigo-600 flex items-center space-x-1 transition-colors"
          >
            <span>{{ t.viewpoints.customBtn }}</span>
          </button>

          <span
            v-if="judgments[vp.id]?.custom_note"
            class="text-[11px] text-purple-600 font-medium truncate max-w-xs"
          >
            已附加批注: “{{ judgments[vp.id]?.custom_note }}”
          </span>
        </div>

        <!-- Custom Note Textarea -->
        <div v-if="showCustomInput[vp.id]" class="mt-2">
          <textarea
            v-model="customNotes[vp.id]"
            @input="updateCustomNote(vp.id)"
            rows="2"
            class="w-full text-xs p-2 rounded border border-indigo-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-indigo-50/30 text-slate-800"
            :placeholder="t.viewpoints.customPlaceholder"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from '../i18n'
import type { CoreViewpoint, ViewpointJudgment } from '../services/api'

const { t } = useI18n()

const props = defineProps<{
  viewpoints: CoreViewpoint[]
}>()

const emit = defineEmits<{
  (e: 'update:judgments', judgments: ViewpointJudgment[]): void
}>()

const isCollapsed = ref(false)
const judgments = ref<Record<string, { selected_key: string; selected_text: string; custom_note?: string }>>({})
const showCustomInput = ref<Record<string, boolean>>({})
const customNotes = ref<Record<string, string>>({})

const initJudgments = () => {
  if (!props.viewpoints) return
  props.viewpoints.forEach((vp) => {
    if (!judgments.value[vp.id]) {
      const defaultOpt = vp.options.find((o) => o.key === 'agree') || vp.options[0]
      judgments.value[vp.id] = {
        selected_key: defaultOpt ? defaultOpt.key : 'agree',
        selected_text: defaultOpt ? defaultOpt.text : vp.claim,
      }
    }
  })
  emitJudgments()
}

onMounted(() => {
  initJudgments()
})

watch(
  () => props.viewpoints,
  () => {
    initJudgments()
  },
  { deep: true }
)

const isOptionSelected = (vpId: string, key: string) => {
  return judgments.value[vpId]?.selected_key === key
}

const selectOption = (vp: CoreViewpoint, key: string, text: string) => {
  judgments.value[vp.id] = {
    ...judgments.value[vp.id],
    selected_key: key,
    selected_text: text,
  }
  emitJudgments()
}

const toggleCustomNote = (vpId: string) => {
  showCustomInput.value[vpId] = !showCustomInput.value[vpId]
}

const updateCustomNote = (vpId: string) => {
  if (judgments.value[vpId]) {
    judgments.value[vpId].custom_note = customNotes.value[vpId]?.trim() || undefined
    emitJudgments()
  }
}

const emitJudgments = () => {
  const result: ViewpointJudgment[] = props.viewpoints.map((vp) => {
    const current = judgments.value[vp.id] || {
      selected_key: 'agree',
      selected_text: vp.claim,
    }
    return {
      viewpoint_id: vp.id,
      claim: vp.claim,
      selected_key: current.selected_key,
      selected_text: current.selected_text,
      custom_note: current.custom_note,
    }
  })
  emit('update:judgments', result)
}

const activeContrarianCount = computed(() => {
  return Object.values(judgments.value).filter(
    (j) => j.selected_key !== 'agree' || (j.custom_note && j.custom_note.trim())
  ).length
})

const getCardBorderClass = (vpId: string) => {
  const j = judgments.value[vpId]
  if (j && j.selected_key === 'counter') {
    return 'border-purple-300 bg-purple-50/20'
  }
  if (j && j.selected_key === 'nuanced') {
    return 'border-blue-300 bg-blue-50/20'
  }
  return 'border-slate-200'
}

const getOptionButtonClass = (vpId: string, key: string) => {
  const isSelected = isOptionSelected(vpId, key)
  if (isSelected) {
    if (key === 'agree') {
      return 'border-emerald-500 bg-emerald-50/70 text-emerald-900 shadow-sm ring-1 ring-emerald-400'
    }
    if (key === 'counter') {
      return 'border-purple-500 bg-purple-50/70 text-purple-900 shadow-sm ring-1 ring-purple-400 font-bold'
    }
    return 'border-blue-500 bg-blue-50/70 text-blue-900 shadow-sm ring-1 ring-blue-400'
  }
  return 'border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 bg-white'
}
</script>
