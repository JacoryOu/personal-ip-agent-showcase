// Visual theme tokens shared by every renderer.

import type { VisualTheme } from './types'

export const THEMES: Record<VisualTheme, {
  bgStart: string
  bgEnd: string
  cardBg: string
  cardBorder: string
  primaryText: string
  secondaryText: string
  accentColor: string
  tagBg: string
  tagText: string
  goldColor: string
}> = {
  dark_gold: {
    bgStart: '#0f172a',
    bgEnd: '#1e1b4b',
    cardBg: 'rgba(30, 41, 59, 0.75)',
    cardBorder: 'rgba(234, 179, 8, 0.35)',
    primaryText: '#f8fafc',
    secondaryText: '#94a3b8',
    accentColor: '#fbbf24',
    tagBg: 'rgba(234, 179, 8, 0.15)',
    tagText: '#fde047',
    goldColor: '#f59e0b',
  },
  indigo_purple: {
    bgStart: '#1e1b4b',
    bgEnd: '#4c1d95',
    cardBg: 'rgba(255, 255, 255, 0.08)',
    cardBorder: 'rgba(167, 139, 250, 0.4)',
    primaryText: '#ffffff',
    secondaryText: '#c4b5fd',
    accentColor: '#38bdf8',
    tagBg: 'rgba(56, 189, 248, 0.18)',
    tagText: '#7dd3fc',
    goldColor: '#38bdf8',
  },
  clean_minimal: {
    bgStart: '#f8fafc',
    bgEnd: '#f1f5f9',
    cardBg: '#ffffff',
    cardBorder: 'rgba(203, 213, 225, 0.9)',
    primaryText: '#0f172a',
    secondaryText: '#475569',
    accentColor: '#2563eb',
    tagBg: 'rgba(37, 99, 235, 0.1)',
    tagText: '#1d4ed8',
    goldColor: '#2563eb',
  },
}
