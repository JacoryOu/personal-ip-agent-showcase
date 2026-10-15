// doocs/md theme palette configuration.
//
// The four doocs themes (Emerald, Ocean Blue, Sunset Orange, Cyber Purple)
// and their colour configuration. Theme keys live in ./types.

import type { DoocsThemeKey } from './types'

export interface DoocsThemeConfig {
  id: DoocsThemeKey
  name: string
  nameZh: string
  emoji: string
  primary: string
  secondary: string
  accentBg: string
  border: string
  badgeText: string
  titleColor: string
  desc: string
}

export const DOOCS_THEMES: Record<DoocsThemeKey, DoocsThemeConfig> = {
  emerald: {
    id: 'emerald',
    name: 'Classic Emerald',
    nameZh: '翡翠绿',
    emoji: '🍃',
    primary: '#10b981',
    secondary: '#059669',
    accentBg: '#ecfdf5',
    border: '#a7f3d0',
    badgeText: '#ffffff',
    titleColor: '#064e3b',
    desc: '深度商业洞察、技术解析最佳搭档',
  },
  ocean: {
    id: 'ocean',
    name: 'Ocean Blue',
    nameZh: '商务蓝',
    emoji: '🌊',
    primary: '#2563eb',
    secondary: '#1d4ed8',
    accentBg: '#eff6ff',
    border: '#bfdbfe',
    badgeText: '#ffffff',
    titleColor: '#1e3a8a',
    desc: '职场干货、方法论与深度长文首选',
  },
  orange: {
    id: 'orange',
    name: 'Sunset Orange',
    nameZh: '活力橙',
    emoji: '🍊',
    primary: '#f97316',
    secondary: '#ea580c',
    accentBg: '#fff7ed',
    border: '#fed7aa',
    badgeText: '#ffffff',
    titleColor: '#7c2d12',
    desc: '个人成长、新消费与情感共鸣热文',
  },
  purple: {
    id: 'purple',
    name: 'Cyber Purple',
    nameZh: '暗夜紫',
    emoji: '🔮',
    primary: '#7c3aed',
    secondary: '#6d28d9',
    accentBg: '#f5f3ff',
    border: '#ddd6fe',
    badgeText: '#ffffff',
    titleColor: '#4c1d95',
    desc: '前沿科技、AI与认知升级先锋视觉',
  },
}
