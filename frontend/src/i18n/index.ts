import { ref, computed } from 'vue'
import { zh } from './locales/zh'
import { en } from './locales/en'

export type Locale = 'zh' | 'en'

const savedLocale = (localStorage.getItem('app_locale') as Locale) || 'zh'
export const currentLocale = ref<Locale>(savedLocale)

export function setLocale(locale: Locale) {
  currentLocale.value = locale
  localStorage.setItem('app_locale', locale)
}

export function toggleLocale() {
  setLocale(currentLocale.value === 'zh' ? 'en' : 'zh')
}

export const messages = {
  zh,
  en,
}

export function useI18n() {
  const t = computed(() => messages[currentLocale.value])
  return {
    locale: currentLocale,
    setLocale,
    toggleLocale,
    t,
  }
}
