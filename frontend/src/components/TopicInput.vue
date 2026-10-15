<template>
  <div class="max-w-4xl mx-auto p-6 bg-white rounded-2xl shadow-lg border border-slate-200/80 glass-card scroll-reveal">
    <div class="text-center mb-6">
      <h2 class="text-2xl font-bold text-gray-800">{{ t.topic.title }}</h2>
      <p class="text-gray-500 mt-2 text-sm">
        {{ t.topic.desc }}
      </p>
    </div>

    <form @submit.prevent="handleSubmit" class="space-y-4">
      <div>
        <label for="topic" class="block text-sm font-semibold text-gray-700 mb-1">
          {{ t.topic.label }} <span class="text-red-500">*</span>
        </label>
        <div class="relative">
          <input
            id="topic"
            v-model="topic"
            type="text"
            maxlength="500"
            :disabled="loading"
            :placeholder="t.topic.placeholder"
            class="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all duration-200 text-gray-800 disabled:bg-gray-100 disabled:cursor-not-allowed shadow-2xs"
            :class="[hasError ? 'border-red-400 focus:ring-red-400' : 'border-gray-300 focus:border-indigo-500']"
          />
        </div>
        <p v-if="hasError" class="text-red-500 text-xs mt-1">{{ t.topic.error }}</p>
      </div>

      <!-- Quick Suggestion Chips -->
      <div class="flex flex-wrap items-center gap-2 pt-1">
        <span class="text-xs text-gray-400 font-medium">{{ t.topic.quickIdeas }}</span>
        <button
          v-for="chip in t.topic.chips"
          :key="chip"
          type="button"
          :disabled="loading"
          @click="topic = chip; hasError = false"
          class="text-xs bg-gray-100 hover:bg-blue-50 hover:text-blue-600 text-gray-600 px-3 py-1 rounded-full transition-colors duration-150 disabled:opacity-50"
        >
          {{ chip }}
        </button>
      </div>

      <!-- Quick Options: Additional Context & One-Click Deconstruct -->
      <div class="pt-2">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <button
            type="button"
            @click="showContext = !showContext"
            class="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center space-x-1 focus:outline-none cursor-pointer"
          >
            <span>{{ showContext ? t.topic.hideContext : t.topic.addContext }}</span>
          </button>

          <button
            type="button"
            @click="$emit('open-deconstruct')"
            class="text-xs font-bold text-amber-700 hover:text-amber-900 flex items-center gap-1 bg-amber-50 hover:bg-amber-100 border border-amber-200 px-3 py-1 rounded-full transition cursor-pointer active:scale-95"
            title="Paste an external viral article to extract its structural skeleton and emotional arc"
          >
            <span>⚡</span>
            <span>粘贴爆款一键拆骨</span>
          </button>
        </div>
        <div v-if="showContext" class="mt-2">
          <textarea
            v-model="additionalContext"
            rows="2"
            :disabled="loading"
            :placeholder="t.topic.contextPlaceholder"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none transition-colors duration-200 text-gray-700 disabled:bg-gray-100"
          ></textarea>
        </div>
      </div>

      <!-- Submit Button -->
      <div class="pt-3">
        <button
          type="submit"
          :disabled="loading || !topic.trim()"
          class="w-full py-3 px-6 rounded-lg font-bold text-white transition-all duration-200 shadow-md flex items-center justify-center space-x-2"
          :class="[
            loading || !topic.trim()
              ? 'bg-blue-300 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 hover:shadow-lg active:scale-[0.99]'
          ]"
        >
          <svg
            v-if="loading"
            class="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span>{{ loading ? t.topic.generating : t.topic.submit }}</span>
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from '../i18n'

const { t } = useI18n()

const props = defineProps<{
  loading?: boolean
  initialTopic?: string
  initialContext?: string
}>()

const emit = defineEmits<{
  (e: 'submit', payload: { topic: string; additionalContext?: string }): void
  (e: 'open-deconstruct'): void
}>()

const topic = ref(props.initialTopic || '')
const additionalContext = ref(props.initialContext || '')
const showContext = ref(Boolean(props.initialContext))
const hasError = ref(false)

watch(
  () => props.initialTopic,
  (val) => {
    if (val !== undefined && val !== topic.value) {
      topic.value = val
    }
  }
)
watch(
  () => props.initialContext,
  (val) => {
    if (val !== undefined && val !== additionalContext.value) {
      additionalContext.value = val
      if (val) showContext.value = true
    }
  }
)


const handleSubmit = () => {
  if (!topic.value.trim()) {
    hasError.value = true
    return
  }
  hasError.value = false
  emit('submit', {
    topic: topic.value.trim(),
    additionalContext: additionalContext.value.trim() || undefined,
  })
}
</script>
