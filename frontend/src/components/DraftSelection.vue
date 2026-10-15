<template>
  <div class="max-w-6xl mx-auto p-6 bg-white rounded-2xl shadow-lg border border-slate-200/80 glass-card scroll-reveal">
    <div class="text-center mb-8">
      <h2 class="text-2xl font-bold text-gray-800">{{ t.outline.title }}</h2>
      <p class="text-gray-500 mt-2">{{ t.outline.desc }}</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <!-- Draft A Card -->
      <div 
        class="relative flex flex-col p-6 rounded-2xl border-2 transition-all duration-300 hover:shadow-xl cursor-pointer scroll-reveal"
        :class="[selectedDraft === 'A' ? 'border-blue-500 bg-blue-50/50 shadow-md ring-2 ring-blue-400/20' : 'border-gray-200 hover:border-blue-300 bg-white']"
        @click="selectDraft('A')"
      >
        <div v-if="selectedDraft === 'A'" class="absolute -top-3 -right-3 bg-blue-500 text-white p-1 rounded-full shadow-md">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        
        <div class="mb-4">
          <span class="inline-block px-3 py-1 bg-blue-100 text-blue-700 font-semibold rounded-full text-sm mb-3">{{ t.outline.optionA }}</span>
          <h3 class="text-xl font-bold text-gray-900">{{ draftA.title }}</h3>
          <p class="text-gray-600 mt-2 text-sm">{{ draftA.summary }}</p>
        </div>
        
        <div class="flex-grow">
          <h4 class="font-semibold text-gray-700 text-sm uppercase tracking-wide mb-3">{{ t.outline.structure }}</h4>
          <ul class="space-y-3">
            <li v-for="(item, index) in draftA.structure" :key="index" class="flex items-start">
              <span class="flex-shrink-0 h-6 w-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold mr-3">{{ index + 1 }}</span>
              <span class="text-gray-700 text-sm leading-tight mt-0.5">{{ item }}</span>
            </li>
          </ul>
        </div>
        
        <div class="mt-8 pt-4 border-t border-gray-100">
          <button 
            type="button"
            class="w-full py-3 px-4 rounded-lg font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            :class="[selectedDraft === 'A' ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-100 text-gray-700 hover:bg-gray-200']"
            @click.stop="selectDraft('A')"
          >
            {{ selectedDraft === 'A' ? t.outline.selected : t.outline.selectA }}
          </button>
        </div>
      </div>

      <!-- Draft B Card -->
      <div 
        class="relative flex flex-col p-6 rounded-2xl border-2 transition-all duration-300 hover:shadow-xl cursor-pointer scroll-reveal"
        :class="[selectedDraft === 'B' ? 'border-purple-500 bg-purple-50/50 shadow-md ring-2 ring-purple-400/20' : 'border-gray-200 hover:border-purple-300 bg-white']"
        @click="selectDraft('B')"
      >
        <div v-if="selectedDraft === 'B'" class="absolute -top-3 -right-3 bg-purple-500 text-white p-1 rounded-full shadow-md">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <div class="mb-4">
          <span class="inline-block px-3 py-1 bg-purple-100 text-purple-700 font-semibold rounded-full text-sm mb-3">{{ t.outline.optionB }}</span>
          <h3 class="text-xl font-bold text-gray-900">{{ draftB.title }}</h3>
          <p class="text-gray-600 mt-2 text-sm">{{ draftB.summary }}</p>
        </div>
        
        <div class="flex-grow">
          <h4 class="font-semibold text-gray-700 text-sm uppercase tracking-wide mb-3">{{ t.outline.structure }}</h4>
          <ul class="space-y-3">
            <li v-for="(item, index) in draftB.structure" :key="index" class="flex items-start">
              <span class="flex-shrink-0 h-6 w-6 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center text-xs font-bold mr-3">{{ index + 1 }}</span>
              <span class="text-gray-700 text-sm leading-tight mt-0.5">{{ item }}</span>
            </li>
          </ul>
        </div>
        
        <div class="mt-8 pt-4 border-t border-gray-100">
          <button 
            type="button"
            class="w-full py-3 px-4 rounded-xl font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 active:scale-95"
            :class="[selectedDraft === 'B' ? 'bg-purple-600 text-white hover:bg-purple-700 shadow-md' : 'bg-gray-100 text-gray-700 hover:bg-gray-200']"
            @click.stop="selectDraft('B')"
          >
            {{ selectedDraft === 'B' ? t.outline.selected : t.outline.selectB }}
          </button>
        </div>
      </div>
    </div>
    
    <div v-if="selectedDraft" class="mt-8 flex justify-center toast-enter">
      <button 
        type="button"
        class="px-8 py-3 bg-gray-900 text-white font-bold rounded-xl hover:bg-gray-800 transition-all shadow-lg hover:shadow-xl focus:ring-4 focus:ring-gray-300 flex items-center justify-center space-x-2 disabled:opacity-75 disabled:cursor-not-allowed active:scale-95"
        :disabled="loading"
        @click="confirmSelection"
      >
        <svg
          v-if="loading"
          class="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>{{ loading ? t.outline.generatingDraft : t.outline.confirm }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { PropType } from 'vue'
import { useI18n } from '../i18n'

const { t } = useI18n()

export interface Draft {
  title: string
  summary: string
  structure: string[]
}

const props = defineProps({
  draftA: {
    type: Object as PropType<Draft>,
    default: () => ({
      title: 'Analytical & Direct',
      summary: 'A structured, logic-first approach focusing on data and clear arguments. Ideal for professional audiences.',
      structure: [
        'Introduction: Problem Statement',
        'Data Analysis & Trends',
        'Core Argument Formulation',
        'Case Studies / Evidence',
        'Conclusion & Call to Action'
      ]
    })
  },
  draftB: {
    type: Object as PropType<Draft>,
    default: () => ({
      title: 'Narrative & Emotional',
      summary: 'A story-driven approach that builds connection through personal anecdotes and emotional resonance.',
      structure: [
        'The Hook: A Personal Story',
        'The Conflict & Emotional Stakes',
        'The Journey of Discovery',
        'The Turning Point / Epiphany',
        'Resolution & Broader Implications'
      ]
    })
  },
  initialSelected: {
    type: String as PropType<string | null>,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm'])

const selectedDraft = ref<string | null>(props.initialSelected || 'A')

watch(() => props.initialSelected, (newVal) => {
  if (newVal) {
    selectedDraft.value = newVal
  }
})

const selectDraft = (option: string) => {
  selectedDraft.value = option
}

const confirmSelection = () => {
  if (selectedDraft.value) {
    emit('confirm', selectedDraft.value)
  }
}
</script>

<style scoped>
.fade-in {
  animation: fadeIn 0.4s ease-in-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
