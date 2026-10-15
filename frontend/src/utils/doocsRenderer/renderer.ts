import { DOOCS_THEMES } from './themes'
import type { DoocsThemeConfig } from './themes'
import type { DoocsRenderOptions, DoocsThemeKey, SectionIllustration } from './types'
import { escapeHtml, stripMarkdown } from './markdown'

/** Internal reference to a markdown link extracted into the footnote block */
interface FootnoteReference {
  index: number
  text: string
  url: string
}

/**
 * Main doocs/md WeChat HTML renderer.
 * Formats Markdown into 100% inline-styled, WeChat MP compliant HTML.
 */
export function renderWechatHtmlWithDoocs(
  markdown: string,
  options: DoocsRenderOptions = {}
): string {
  const themeKey = (options.theme && DOOCS_THEMES[options.theme as DoocsThemeKey])
    ? (options.theme as DoocsThemeKey)
    : 'emerald'
  const theme = DOOCS_THEMES[themeKey]
  const enableFootnotes = options.enableFootnotes !== false
  const includeHeaderInBody = options.includeHeaderInBody !== false
  let skippedInitialH1 = false

  // Track illustrations by index and section title
  const illustrationsMap = new Map<number | string, SectionIllustration>()
  const usedIllustrations = new Set<string>()

  if (options.illustrations && options.illustrations.length > 0) {
    options.illustrations.forEach((item, idx) => {
      if (item.image_url) {
        illustrationsMap.set(item.section_index ?? (idx + 1), item)
        illustrationsMap.set(item.section_title.trim(), item)
        illustrationsMap.set(stripMarkdown(item.section_title).trim(), item)
      }
    })
  }

  function getIllustrationForHeading(index: number, title: string): SectionIllustration | undefined {
    const clean = stripMarkdown(title).trim()
    const ill = illustrationsMap.get(index) || illustrationsMap.get(clean) || illustrationsMap.get(title.trim())
    if (ill && ill.image_url) {
      const idKey = ill.id || `ill_${index}`
      if (!usedIllustrations.has(idKey)) {
        usedIllustrations.add(idKey)
        return ill
      }
    }
    return undefined
  }

  function renderIllustrationFigure(ill: SectionIllustration): string {
    const caption = escapeHtml(ill.caption || ill.section_title)
    return `
<figure style="margin: 24px 0; text-align: center;">
  <img src="${ill.image_url}" alt="${caption}" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); display: block; margin: 0 auto;" />
  <figcaption style="margin-top: 8px; font-size: 13px; color: #64748b; text-align: center; font-style: italic; letter-spacing: 0.3px;">
    ${caption}
  </figcaption>
</figure>`
  }

  // Step 1: Pre-process Code Blocks to protect them from Markdown parsing
  const codeBlocks: string[] = []
  let content = markdown.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const placeholder = `@@DOOCSCODEBLOCK${codeBlocks.length}@@`
    const escapedCode = escapeHtml(code.trimEnd())
    const langLabel = (lang || 'code').toUpperCase()
    
    const codeHtml = `
<div style="margin: 24px 0; border-radius: 10px; background-color: #282c34; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); overflow: hidden;">
  <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background-color: #21252b; border-bottom: 1px solid rgba(255, 255, 255, 0.08); user-select: none;">
    <div style="display: flex; align-items: center; gap: 6px;">
      <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background-color: #ff5f56;"></span>
      <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background-color: #ffbd2e;"></span>
      <span style="display: inline-block; width: 11px; height: 11px; border-radius: 50%; background-color: #27c93f;"></span>
    </div>
    <span style="font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, Menlo, Monaco, Consolas, monospace; color: #828997; font-weight: 600; letter-spacing: 0.5px;">${langLabel}</span>
  </div>
  <pre style="margin: 0; padding: 14px 16px; overflow-x: auto; font-family: Menlo, Monaco, Consolas, 'Courier New', monospace; font-size: 13.5px; line-height: 24px; color: #abb2bf; background-color: #282c34; word-break: normal; white-space: pre;"><code style="font-family: inherit; font-size: inherit; color: inherit; background: transparent; padding: 0; line-height: 24px;">${escapedCode}</code></pre>
</div>`
    codeBlocks.push(codeHtml)
    return placeholder
  })

  // Step 2: Pre-process Inline Code blocks to protect them from footnote/emphasis parsing
  const inlineCodes: string[] = []
  content = content.replace(/`([^`\n]+)`/g, (_m, code) => {
    const placeholder = `@@DOOCSINLINECODE${inlineCodes.length}@@`
    const codeHtml = `<code style="font-family: Menlo, Monaco, Consolas, monospace; font-size: 13.5px; background-color: ${theme.accentBg}; color: ${theme.primary}; padding: 2px 6px; border-radius: 4px; margin: 0 2px; border: 1px solid ${theme.border};">${escapeHtml(code)}</code>`
    inlineCodes.push(codeHtml)
    return placeholder
  })

  // Step 3: Extract Footnote References (WeChat does not support clickable external <a> links)
  const footnotes: FootnoteReference[] = []
  if (enableFootnotes) {
    content = content.replace(/(?<!\!)\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_match, text, url) => {
      footnotes.push({
        index: footnotes.length + 1,
        text: text.trim(),
        url: url.trim(),
      })
      const refIdx = footnotes.length
      return `<span style="color: ${theme.primary}; font-weight: 500; border-bottom: 1px dashed ${theme.primary};">${text}</span><sup style="color: ${theme.primary}; font-size: 11px; margin-left: 2px; font-weight: 700;">[${refIdx}]</sup>`
    })
  }

  // Step 4: Line-by-line AST compilation
  const lines = content.split('\n')
  const htmlBlocks: string[] = []
  let h2Count = 0
  let h3Count = 0

  // Buffers for stateful blocks
  let inBlockquote = false
  let blockquoteBuffer: string[] = []

  let inList = false
  let listItemsBuffer: { text: string; checked?: boolean }[] = []
  let listType: 'ul' | 'ol' | 'task' = 'ul'

  let inTable = false
  let tableRowsBuffer: string[] = []

  let paragraphBuffer: string[] = []

  function flushParagraph() {
    if (paragraphBuffer.length === 0) return
    const text = paragraphBuffer.join('\n').trim()
    paragraphBuffer = []
    if (!text) return

    const formatted = formatInline(text, theme, inlineCodes)
      .replace(/\n/g, '<br />')

    htmlBlocks.push(`
<p style="margin: 0 0 16px 0; font-size: 15.5px; color: #333333; line-height: 28px; text-align: justify; letter-spacing: 0.5px; word-break: break-word;">
  ${formatted}
</p>`)
  }

  function flushBlockquote() {
    if (!inBlockquote || blockquoteBuffer.length === 0) return
    const rawQuote = blockquoteBuffer.join('\n').trim()
    blockquoteBuffer = []
    inBlockquote = false

    const calloutMatch = rawQuote.match(/^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*([\s\S]*)$/i)
    if (calloutMatch) {
      const type = calloutMatch[1].toUpperCase()
      const quoteBody = calloutMatch[2].trim()
      let calloutColor = theme.primary
      let calloutBg = theme.accentBg
      let calloutIcon = '💡'
      let calloutLabel = '重点洞察'

      if (type === 'NOTE') {
        calloutColor = '#2563eb'
        calloutBg = '#eff6ff'
        calloutIcon = 'ℹ️'
        calloutLabel = '参考提示'
      } else if (type === 'WARNING' || type === 'CAUTION') {
        calloutColor = '#f59e0b'
        calloutBg = '#fffbeb'
        calloutIcon = '⚠️'
        calloutLabel = '注意与避坑'
      } else if (type === 'IMPORTANT') {
        calloutColor = '#7c3aed'
        calloutBg = '#f5f3ff'
        calloutIcon = '📌'
        calloutLabel = '关键结论'
      }

      htmlBlocks.push(`
<section style="margin: 22px 0; padding: 14px 18px; background-color: ${calloutBg}; border: 1px solid ${calloutColor}40; border-left: 4px solid ${calloutColor}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02); line-height: 26px;">
  <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-size: 13.5px; font-weight: 700; color: ${calloutColor}; line-height: 22px;">
    <span>${calloutIcon}</span>
    <span>${calloutLabel}</span>
  </div>
  <div style="font-size: 14.5px; line-height: 26px; color: #334155;">
    ${formatInline(quoteBody, theme, inlineCodes).replace(/\n/g, '<br />')}
  </div>
</section>`)
      return
    }

    htmlBlocks.push(`
<blockquote style="margin: 20px 0; padding: 14px 18px; background-color: ${theme.accentBg}; border-left: 4px solid ${theme.primary}; color: #475569; font-size: 14.5px; line-height: 26px; border-radius: 0 8px 8px 0; letter-spacing: 0.3px;">
  ${formatInline(rawQuote, theme, inlineCodes).replace(/\n/g, '<br />')}
</blockquote>`)
  }

  function flushList() {
    if (!inList || listItemsBuffer.length === 0) return
    const items = listItemsBuffer.map((it, idx) => {
      let bulletHtml = ''
      if (listType === 'task') {
        const isChecked = it.checked
        const checkIcon = isChecked ? '✓' : ''
        const bg = isChecked ? theme.primary : 'transparent'
        const border = isChecked ? theme.primary : '#94a3b8'
        const color = isChecked ? '#ffffff' : 'transparent'
        bulletHtml = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; border-radius: 4px; border: 1.5px solid ${border}; background-color: ${bg}; color: ${color}; font-size: 10px; font-weight: 900; margin-right: 8px; line-height: 15px; vertical-align: middle; flex-shrink: 0;">${checkIcon}</span>`
      } else if (listType === 'ol') {
        bulletHtml = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background-color: ${theme.primary}20; color: ${theme.primary}; font-size: 10.5px; font-weight: 800; margin-right: 8px; line-height: 18px; vertical-align: middle; flex-shrink: 0;">${idx + 1}</span>`
      } else {
        bulletHtml = `<span style="display: inline-block; color: ${theme.primary}; font-weight: bold; font-size: 13px; margin-right: 8px; line-height: 28px; vertical-align: middle; flex-shrink: 0;">●</span>`
      }

      return `<li style="margin-bottom: 8px; font-size: 15px; color: #334155; line-height: 28px; display: flex; align-items: baseline; text-align: justify; list-style: none;">${bulletHtml}<span style="line-height: 28px; flex: 1 1 0%;">${formatInline(it.text, theme, inlineCodes)}</span></li>`
    }).join('\n')

    htmlBlocks.push(`<ul style="margin: 16px 0; padding-left: 2px; list-style: none;">\n${items}\n</ul>`)
    listItemsBuffer = []
    inList = false
  }

  function flushTable() {
    if (!inTable || tableRowsBuffer.length === 0) return
    const rows = [...tableRowsBuffer]
    tableRowsBuffer = []
    inTable = false

    if (rows.length < 2) {
      rows.forEach(r => paragraphBuffer.push(r))
      flushParagraph()
      return
    }

    const headerLine = rows[0]
    const alignLine = rows[1]
    const dataLines = rows.slice(2)

    const parseCells = (line: string) => {
      return line
        .replace(/^\|/, '')
        .replace(/\|$/, '')
        .split('|')
        .map(c => c.trim())
    }

    const headers = parseCells(headerLine)
    const alignSpecs = parseCells(alignLine)
    const alignments = alignSpecs.map(spec => {
      const leftColon = spec.startsWith(':')
      const rightColon = spec.endsWith(':')
      if (leftColon && rightColon) return 'center'
      if (rightColon) return 'right'
      return 'left'
    })

    const headerThs = headers.map((h, i) => {
      const align = alignments[i] || 'left'
      return `<th style="padding: 10px 14px; font-weight: 700; color: ${theme.titleColor}; border: 1px solid ${theme.border}; text-align: ${align}; font-size: 13.5px; line-height: 24px; background-color: ${theme.accentBg};">${formatInline(h, theme, inlineCodes)}</th>`
    }).join('')

    const bodyTrs = dataLines.map((line, rIdx) => {
      const cells = parseCells(line)
      const bgColor = rIdx % 2 === 1 ? '#f8fafc' : '#ffffff'
      const tds = headers.map((_, cIdx) => {
        const cellText = cells[cIdx] || ''
        const align = alignments[cIdx] || 'left'
        return `<td style="padding: 10px 14px; color: #334155; border: 1px solid #e2e8f0; text-align: ${align}; font-size: 13.5px; line-height: 24px;">${formatInline(cellText, theme, inlineCodes)}</td>`
      }).join('')
      return `<tr style="background-color: ${bgColor}; border-bottom: 1px solid #f1f5f9;">${tds}</tr>`
    }).join('')

    htmlBlocks.push(`
<section style="margin: 22px 0; overflow-x: auto; -webkit-overflow-scrolling: touch; line-height: 24px;">
  <table style="width: 100%; border-collapse: collapse; font-size: 14px; line-height: 24px; text-align: left; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; margin: 0 auto;">
    <thead>
      <tr style="border-bottom: 2px solid ${theme.border};">
        ${headerThs}
      </tr>
    </thead>
    <tbody>
      ${bodyTrs}
    </tbody>
  </table>
</section>`)
  }

  function flushAllBuffers() {
    flushParagraph()
    flushBlockquote()
    flushList()
    flushTable()
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i]
    const trimmed = rawLine.trim()

    // 1. Code Block placeholder
    if (trimmed.startsWith('@@DOOCSCODEBLOCK')) {
      flushAllBuffers()
      const idx = parseInt(trimmed.replace('@@DOOCSCODEBLOCK', '').replace('@@', ''), 10)
      if (codeBlocks[idx]) {
        htmlBlocks.push(codeBlocks[idx])
      }
      continue
    }

    // 2. Empty line
    if (!trimmed) {
      flushAllBuffers()
      continue
    }

    // 3. Table row
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|')) {
      flushParagraph()
      flushBlockquote()
      flushList()
      inTable = true
      tableRowsBuffer.push(trimmed)
      continue
    } else {
      flushTable()
    }

    // 4. Blockquote
    if (trimmed.startsWith('>')) {
      flushParagraph()
      flushList()
      inBlockquote = true
      blockquoteBuffer.push(trimmed.replace(/^>\s?/, ''))
      continue
    } else {
      flushBlockquote()
    }

    // 5. Lists (Checklists, Unordered, Ordered)
    const taskMatch = trimmed.match(/^[-*]\s+\[([ xX])\]\s+(.*)$/)
    if (taskMatch) {
      flushParagraph()
      if (!inList || listType !== 'task') {
        flushList()
        inList = true
        listType = 'task'
      }
      listItemsBuffer.push({
        text: taskMatch[2],
        checked: taskMatch[1].toLowerCase() === 'x',
      })
      continue
    }

    if (/^[-*]\s+/.test(trimmed)) {
      flushParagraph()
      if (!inList || listType !== 'ul') {
        flushList()
        inList = true
        listType = 'ul'
      }
      listItemsBuffer.push({ text: trimmed.replace(/^[-*]\s+/, '') })
      continue
    } else if (/^\d+\.\s+/.test(trimmed)) {
      flushParagraph()
      if (!inList || listType !== 'ol') {
        flushList()
        inList = true
        listType = 'ol'
      }
      listItemsBuffer.push({ text: trimmed.replace(/^\d+\.\s+/, '') })
      continue
    } else {
      flushList()
    }

    // 6. Heading 1 (#)
    if (trimmed.startsWith('# ') && !trimmed.startsWith('## ')) {
      flushParagraph()
      const headingText = trimmed.replace(/^#\s+/, '').replace(/#+$/, '').trim()
      if (!includeHeaderInBody && !skippedInitialH1) {
        skippedInitialH1 = true
        continue
      }
      // Avoid duplicate title if options.title was already rendered
      if (includeHeaderInBody && options.title && (stripMarkdown(headingText).trim() === stripMarkdown(options.title).trim() || headingText.trim() === options.title.trim())) {
        continue
      }
      htmlBlocks.push(`
<h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin: 30px 0 18px 0; padding-left: 12px; border-left: 4px solid ${theme.primary}; line-height: 36px; letter-spacing: 0.5px;">
  ${formatInline(headingText, theme, inlineCodes)}
</h1>`)
      continue
    }

    // 7. Heading 2 (##)
    if (trimmed.startsWith('## ') && !trimmed.startsWith('### ')) {
      flushParagraph()
      h2Count++
      const headingText = trimmed.replace(/^##\s+/, '').replace(/#+$/, '').trim()
      const cleanTitle = stripMarkdown(headingText)
        .replace(/^[\d一二三四五六七八九十]+[、.\s\/-]+/, '')
        .replace(/^[\p{Extended_Pictographic}\uFE0F]\s*/u, '')
        .replace(/^【.*?】\s*/, '')
        .replace(/^[\p{Extended_Pictographic}\uFE0F]\s*/u, '')
        .trim()
      const badgeNumber = String(h2Count).padStart(2, '0')

      htmlBlocks.push(`
<section style="margin-top: 36px; margin-bottom: 18px; display: flex; align-items: center; gap: 8px; line-height: 30px;">
  <span style="display: inline-flex; align-items: center; justify-content: center; background-color: ${theme.primary}; color: #ffffff; padding: 2px 10px; border-radius: 14px; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; line-height: 20px; box-shadow: 0 2px 6px ${theme.primary}40;">${badgeNumber}</span>
  <span style="font-size: 18px; font-weight: 800; color: #0f172a; border-bottom: 2px solid ${theme.primary}; padding-bottom: 3px; line-height: 30px; letter-spacing: 0.3px;">${formatInline(cleanTitle || headingText, theme, inlineCodes)}</span>
</section>`)

      const ill = getIllustrationForHeading(h2Count, cleanTitle || headingText)
      if (ill) {
        htmlBlocks.push(renderIllustrationFigure(ill))
      }
      continue
    }

    // 8. Heading 3 (###)
    if (trimmed.startsWith('### ') && !trimmed.startsWith('#### ')) {
      flushParagraph()
      h3Count++
      const headingText = trimmed.replace(/^###\s+/, '').replace(/#+$/, '').trim()
      htmlBlocks.push(`
<section style="margin-top: 26px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; line-height: 28px;">
  <span style="display: inline-block; width: 5px; height: 16px; background-color: ${theme.primary}; border-radius: 3px; flex-shrink: 0;"></span>
  <span style="font-size: 16px; font-weight: 700; color: #1e293b; line-height: 28px; letter-spacing: 0.2px;">${formatInline(headingText, theme, inlineCodes)}</span>
</section>`)

      if (h2Count === 0) {
        const ill = getIllustrationForHeading(h3Count, headingText)
        if (ill) {
          htmlBlocks.push(renderIllustrationFigure(ill))
        }
      }
      continue
    }

    // 9. Heading 4 (####)
    if (trimmed.startsWith('#### ')) {
      flushParagraph()
      const headingText = trimmed.replace(/^####\s+/, '').replace(/#+$/, '').trim()
      htmlBlocks.push(`
<h4 style="margin: 20px 0 10px 0; font-size: 15px; font-weight: 700; color: #334155; line-height: 26px;">
  ${formatInline(headingText, theme, inlineCodes)}
</h4>`)
      continue
    }

    // 10. Horizontal Rule (---, ***, ___)
    if (/^([-*_]){3,}$/.test(trimmed)) {
      flushParagraph()
      htmlBlocks.push(`<hr style="margin: 32px 0; border: none; border-top: 1px dashed ${theme.border};" />`)
      continue
    }

    // 11. Image
    const imgMatch = trimmed.match(/^!\[([^\]]*)\]\((.+?)\)$/)
    if (imgMatch) {
      flushParagraph()
      const alt = imgMatch[1] || ''
      const url = imgMatch[2].trim()
      htmlBlocks.push(`
<figure style="margin: 22px 0; text-align: center;">
  <img src="${url}" alt="${escapeHtml(alt)}" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); display: block; margin: 0 auto;" />
  ${alt ? `<figcaption style="margin-top: 8px; font-size: 13px; color: #64748b; text-align: center; font-style: italic; line-height: 22px;">${escapeHtml(alt)}</figcaption>` : ''}
</figure>`)
      continue
    }

    // 12. Accumulate lines in paragraph buffer
    paragraphBuffer.push(trimmed)
  }

  // Flush remaining buffers
  flushAllBuffers()

  // If there are illustrations that weren't placed under any heading (e.g. fallback section), insert at the top
  if (options.illustrations && options.illustrations.length > 0) {
    options.illustrations.forEach(ill => {
      if (ill.image_url) {
        const idKey = ill.id || `ill_${ill.section_index || 1}`
        if (!usedIllustrations.has(idKey)) {
          usedIllustrations.add(idKey)
          htmlBlocks.unshift(renderIllustrationFigure(ill))
        }
      }
    })
  }

  // Render Footnotes section at bottom
  let footnotesHtml = ''
  if (enableFootnotes && footnotes.length > 0) {
    const listItems = footnotes.map(fn => {
      const cleanRefText = stripMarkdown(fn.text)
      return `
<li style="margin-bottom: 8px; font-size: 12.5px; color: #64748b; line-height: 22px; word-break: break-all; list-style: none;">
  <span style="font-weight: 700; color: ${theme.primary}; margin-right: 4px; line-height: 22px;">[${fn.index}]</span>
  <span style="line-height: 22px;">${escapeHtml(cleanRefText)}:</span>
  <span style="color: #64748b; font-size: 11.5px; margin-left: 4px; line-height: 22px;">${escapeHtml(fn.url)}</span>
</li>`
    }).join('')

    footnotesHtml = `
<section style="margin-top: 38px; padding-top: 22px; border-top: 1px dashed #cbd5e1; line-height: 24px;">
  <div style="font-size: 14.5px; font-weight: 800; color: ${theme.primary}; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; line-height: 24px;">
    <span>📚</span>
    <span>参考资料与注脚</span>
  </div>
  <ul style="padding-left: 0; list-style: none; margin: 0;">
    ${listItems}
  </ul>
</section>`
  }

  const titleHtml = (includeHeaderInBody && options.title)
    ? `<h1 style="font-size: 23px; font-weight: 800; color: #0f172a; margin: 0 0 20px 0; padding-left: 12px; border-left: 5px solid ${theme.primary}; line-height: 36px; letter-spacing: 0.5px;">${escapeHtml(options.title)}</h1>`
    : ''

  const authorHtml = (includeHeaderInBody && options.author)
    ? `<div style="font-size: 13px; color: #64748b; margin-bottom: 24px; display: flex; align-items: center; gap: 8px; line-height: 22px;">
        <span style="font-weight: 600; color: ${theme.primary}; line-height: 22px;">${escapeHtml(options.author)}</span>
        <span>·</span>
        <span style="line-height: 22px;">个人认知 IP 引擎深度沉淀</span>
      </div>`
    : ''

  return `
<section style="max-width: 677px; margin: 0 auto; padding: 20px 16px; font-size: 15.5px; color: #333333; line-height: 28px; letter-spacing: 0.5px; word-break: break-word; background-color: #ffffff;">
  ${titleHtml}
  ${authorHtml}
  ${htmlBlocks.join('\n')}
  ${footnotesHtml}
</section>`.trim()
}

/**
 * Formats inline typography (bold, italic, del, inline code)
 */
function formatInline(text: string, _theme?: DoocsThemeConfig, inlineCodes: string[] = []): string {
  let res = text

  // Bold (**text** and __text__)
  res = res.replace(/\*\*(.+?)\*\*/g, '<strong style="color: #0f172a; font-weight: 700;">$1</strong>')
  res = res.replace(/__(.+?)__/g, '<strong style="color: #0f172a; font-weight: 700;">$1</strong>')

  // Strikethrough (~~text~~)
  res = res.replace(/~~(.+?)~~/g, '<del style="color: #94a3b8;">$1</del>')

  // Italic (*text* and _text_)
  res = res.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em style="color: #475569; font-style: italic;">$1</em>')
  res = res.replace(/(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g, '<em style="color: #475569; font-style: italic;">$1</em>')

  // Restore inline code placeholders
  res = res.replace(/@@DOOCSINLINECODE(\d+)@@/g, (_m, idxStr) => {
    const idx = parseInt(idxStr, 10)
    return inlineCodes[idx] || ''
  })

  return res
}
