<template>
  <div class="relative inline-block text-left" ref="dropdownContainer">
    <!-- Trigger Pill -->
    <button
      type="button"
      @click="toggleDropdown"
      class="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-white border border-slate-300 shadow-sm text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-all active:scale-95 cursor-pointer select-none"
      :title="t.model.pillTooltip"
      aria-haspopup="true"
      :aria-expanded="isOpen"
    >
      <span class="text-sm leading-none">{{ activeModelPreset.icon }}</span>
      <span class="font-bold text-slate-800 tracking-tight">{{ activeModelDisplayName }}</span>

      <!-- BYOK indicator badge if custom key/endpoint is active -->
      <span
        v-if="hasCustomConfig"
        class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300"
        title="BYOK 自带密钥/代理已生效"
      >
        BYOK
      </span>

      <!-- Dropdown Chevron -->
      <svg
        class="w-3.5 h-3.5 text-slate-400 transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown Menu -->
    <transition
      enter-active-class="transition ease-out duration-150 transform"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition ease-in duration-100 transform"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="isOpen"
        class="absolute right-0 mt-2 w-72 sm:w-80 rounded-2xl bg-white shadow-xl ring-1 ring-black/5 border border-slate-200 p-2 z-50 divide-y divide-slate-100 focus:outline-none"
      >
        <!-- Header -->
        <div class="px-3 py-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold uppercase tracking-wider text-slate-400">
              {{ t.model.dropdownTitle }}
            </span>
            <span
              v-if="hasCustomConfig"
              class="text-[10px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full"
            >
              BYOK 模式
            </span>
          </div>
        </div>

        <!-- Model Presets List -->
        <div class="py-1.5 space-y-1">
          <button
            v-for="preset in MODEL_PRESETS"
            :key="preset.id"
            type="button"
            @click="selectModel(preset.id)"
            class="w-full text-left flex items-start gap-2.5 px-3 py-2 rounded-xl transition-all cursor-pointer group"
            :class="
              currentModel === preset.id
                ? 'bg-blue-50 text-blue-900 font-semibold shadow-xs'
                : 'hover:bg-slate-50 text-slate-700'
            "
          >
            <span class="text-lg leading-none mt-0.5 group-hover:scale-110 transition-transform">
              {{ preset.icon }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold truncate">
                  {{ preset.name }}
                </span>
                <span
                  class="text-[10px] px-1.5 py-0.5 rounded-md font-medium"
                  :class="
                    currentModel === preset.id
                      ? 'bg-blue-200/70 text-blue-800'
                      : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'
                  "
                >
                  {{ locale === 'zh' ? preset.badgeZh : preset.badgeEn }}
                </span>
              </div>
              <p class="text-[11px] text-slate-400 truncate mt-0.5 leading-snug">
                {{ locale === 'zh' ? preset.descriptionZh : preset.descriptionEn }}
              </p>
            </div>
            <!-- Checkmark -->
            <span v-if="currentModel === preset.id" class="text-blue-600 font-black text-xs self-center">
              ✓
            </span>
          </button>
        </div>

        <!-- Footer / Settings Button -->
        <div class="pt-2 pb-1 px-1">
          <button
            type="button"
            @click="handleOpenSettings"
            class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:text-blue-700 hover:bg-blue-50/70 transition-colors border border-dashed border-slate-300 hover:border-blue-300 cursor-pointer"
          >
            <span>⚙️</span>
            <span>{{ t.model.configureBtn }}</span>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from '../i18n'
import {
  currentModel,
  currentProviderId,
  customApiKey,
  customBaseUrl,
  serverModelName,
  activeModelPreset,
  MODEL_PRESETS,
  setCurrentModel,
} from '../services/modelSettings'
import { getCurrentServerSettings } from '../services/api'

const emit = defineEmits<{
  (e: 'open-settings'): void
}>()

const { t, locale } = useI18n()

const isOpen = ref(false)
const dropdownContainer = ref<HTMLElement | null>(null)

const hasCustomConfig = computed(() => {
  return currentProviderId.value !== 'system' && Boolean(customApiKey.value.trim() || customBaseUrl.value.trim())
})

const activeModelDisplayName = computed(() => {
  if (currentModel.value === 'system') {
    return serverModelName.value ? `系统内置 (${serverModelName.value})` : '系统内置默认'
  }
  return activeModelPreset.value.name
})

const toggleDropdown = () => {
  isOpen.value = !isOpen.value
}

const closeDropdown = () => {
  isOpen.value = false
}

const selectModel = (modelId: string) => {
  if (modelId === 'system') {
    currentProviderId.value = 'system'
    setCurrentModel('system')
    closeDropdown()
    return
  }

  // If user picks a custom BYOK model but hasn't entered an API key yet
  if (!customApiKey.value.trim() && modelId !== 'custom') {
    setCurrentModel(modelId)
    closeDropdown()
    emit('open-settings')
    return
  }

  setCurrentModel(modelId)
  closeDropdown()
}

const handleOpenSettings = () => {
  closeDropdown()
  emit('open-settings')
}

// Click-outside listener
const handleClickOutside = (event: MouseEvent) => {
  if (dropdownContainer.value && !dropdownContainer.value.contains(event.target as Node)) {
    closeDropdown()
  }
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  if (!serverModelName.value) {
    try {
      const s = await getCurrentServerSettings()
      serverModelName.value = s.model
    } catch {
      // Graceful fallback
    }
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>