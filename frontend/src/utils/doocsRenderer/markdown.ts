// doocs/md layout & style rendering engine for WeChat Official Accounts.
// See the original module docblock in ../../../utils/doocsRenderer.ts for the full
// feature overview of the Markdown-to-WeChat-HTML compiler.

import type { SectionIllustration } from './types'

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/**
 * Strips markdown symbols like **, *, `, ~~ from text (e.g. for clean titles or captions)
 */
export function stripMarkdown(str: string): string {
  return str
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/~~(.*?)~~/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#+\s*/, '')
    .trim()
}

/**
 * Automatically extracts section titles from Markdown to generate tailored illustration slots
 */
export function extractSectionsFromMarkdown(markdown: string): SectionIllustration[] {
  if (!markdown) return []
  const lines = markdown.split('\n')
  const sections: SectionIllustration[] = []

  // Check if the document contains H2 headings
  const hasH2 = lines.some(l => /^##\s+/.test(l.trim()) && !/^###\s+/.test(l.trim()))
  const targetPrefix = hasH2 ? /^##\s+/ : /^###\s+/

  let sectionIndex = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (targetPrefix.test(line)) {
      const rawTitle = line.replace(targetPrefix, '').replace(/#+$/, '').trim()
      if (rawTitle) {
        sectionIndex++
        const cleanTitle = stripMarkdown(rawTitle)
          .replace(/^[\d一二三四五六七八九十]+[、.\s\/-]+/, '')
          .replace(/^[\p{Extended_Pictographic}\uFE0F]\s*/u, '')
          .replace(/^【.*?】\s*/, '')
          .replace(/^[\p{Extended_Pictographic}\uFE0F]\s*/u, '')
          .trim() || rawTitle

        const promptZh = `极简商业概念摄影，关于「${cleanTitle}」，暗调电影级光影质感，极简构图，艺术留白，16:9 宽屏超清，概念艺术，杰作`
        const promptEn = `Minimalist editorial concept photography about ${cleanTitle}, dramatic cinematic lighting, clean composition, 16:9 ratio, 8k masterpiece`

        sections.push({
          id: `sec_${sectionIndex}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
          section_index: sectionIndex,
          section_title: cleanTitle,
          caption: `图 ${sectionIndex}：${cleanTitle}`,
          prompt: promptZh,
          prompt_zh: promptZh,
          prompt_en: promptEn,
        })
      }
    }
  }

  // Fallback if no headings matched at all
  if (sections.length === 0) {
    const firstLine = stripMarkdown(lines.find(l => l.trim().length > 0) || '核心观点与底层洞察')
    sections.push({
      id: `sec_1_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      section_index: 1,
      section_title: firstLine,
      caption: `图 1：${firstLine}`,
      prompt: `极简商业概念摄影，关于「${firstLine}」，暗调电影级光影质感，极简构图，16:9 宽屏超清`,
      prompt_zh: `极简商业概念摄影，关于「${firstLine}」，暗调电影级光影质感，极简构图，16:9 宽屏超清`,
      prompt_en: `Minimalist editorial photography about ${firstLine}, dramatic cinematic lighting, 16:9 ratio, high quality`,
    })
  }

  return sections
}
