// Xiaohongshu renderers (composite cover + 3:4 card).

import type { XhsCardData, VisualTheme } from './types'
import { THEMES } from './themes'
import { wrapText, drawRoundedRect, loadImage } from './canvasHelpers'

export async function renderXhsCompositeCoverToCanvas(
  cover: XhsCardData,
  bgImageUrl?: string,
  themeKey: VisualTheme = 'dark_gold',
  brandName = '个人认知 IP 引擎',
  curPage = 1,
  totPage = 1
): Promise<HTMLCanvasElement> {
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1440
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas

  const t = THEMES[themeKey]

  // 1. Draw Background: AI generated photo or gradient
  if (bgImageUrl) {
    try {
      const bgImg = await loadImage(bgImageUrl)
      const imgAspect = bgImg.width / bgImg.height
      const canvasAspect = 1080 / 1440
      let sx = 0, sy = 0, sw = bgImg.width, sh = bgImg.height
      if (imgAspect > canvasAspect) {
        sw = bgImg.height * canvasAspect
        sx = (bgImg.width - sw) / 2
      } else {
        sh = bgImg.width / canvasAspect
        sy = (bgImg.height - sh) / 2
      }
      ctx.drawImage(bgImg, sx, sy, sw, sh, 0, 0, 1080, 1440)
    } catch (e) {
      console.warn('Failed to load AI background image, falling back to gradient', e)
      const grad = ctx.createLinearGradient(0, 0, 1080, 1440)
      grad.addColorStop(0, t.bgStart)
      grad.addColorStop(1, t.bgEnd)
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, 1080, 1440)
    }
  } else {
    const grad = ctx.createLinearGradient(0, 0, 1080, 1440)
    grad.addColorStop(0, t.bgStart)
    grad.addColorStop(1, t.bgEnd)
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, 1080, 1440)
  }

  // 2. Cinematic Vignette & Ambient Darkness Overlay
  const darkOverlay = ctx.createLinearGradient(0, 0, 0, 1440)
  darkOverlay.addColorStop(0, 'rgba(15, 23, 42, 0.75)')
  darkOverlay.addColorStop(0.2, 'rgba(15, 23, 42, 0.45)')
  darkOverlay.addColorStop(0.5, 'rgba(15, 23, 42, 0.55)')
  darkOverlay.addColorStop(0.85, 'rgba(15, 23, 42, 0.85)')
  darkOverlay.addColorStop(1, 'rgba(15, 23, 42, 0.95)')
  ctx.fillStyle = darkOverlay
  ctx.fillRect(0, 0, 1080, 1440)

  // 3. Central Frosted Glass / Dark Backdrop Card for Crystal Clear Contrast
  const cardX = 64
  const cardY = 200
  const cardW = 1080 - cardX * 2 // 952px
  const cardH = 960

  ctx.save()
  drawRoundedRect(ctx, cardX, cardY, cardW, cardH, 40)
  ctx.fillStyle = 'rgba(15, 23, 42, 0.72)'
  ctx.fill()
  ctx.lineWidth = 2.5
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)'
  ctx.stroke()
  ctx.restore()

  // 4. Header Bar: Author on left, Badge on right
  ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", sans-serif'
  ctx.fillStyle = '#f8fafc'
  ctx.fillText(cover.author || brandName, cardX + 48, cardY + 76)

  // Badge pill
  const badgeText = cover.badge || '深度干货 · 爆款首图'
  ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  const badgeW = ctx.measureText(badgeText).width + 36
  const badgeX = cardX + cardW - 48 - badgeW
  drawRoundedRect(ctx, badgeX, cardY + 48, badgeW, 42, 21)
  ctx.fillStyle = 'rgba(245, 158, 11, 0.25)'
  ctx.fill()
  ctx.lineWidth = 1.5
  ctx.strokeStyle = '#f59e0b'
  ctx.stroke()
  ctx.fillStyle = '#fde047'
  ctx.fillText(badgeText, badgeX + 18, cardY + 77)

  // Separator line
  ctx.beginPath()
  ctx.moveTo(cardX + 48, cardY + 115)
  ctx.lineTo(cardX + cardW - 48, cardY + 115)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)'
  ctx.lineWidth = 1.5
  ctx.stroke()

  // 5. High-Contrast Bold Big Title (68-72px)
  ctx.save()
  ctx.font = '900 70px -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", sans-serif'
  ctx.shadowColor = 'rgba(0, 0, 0, 0.8)'
  ctx.shadowBlur = 18
  ctx.shadowOffsetY = 4
  ctx.fillStyle = '#ffffff'

  const rawTitle = cover.title || '核心干货复盘'
  const titleLines = wrapText(ctx, rawTitle, cardW - 96)
  let curY = cardY + 230
  for (const line of titleLines.slice(0, 3)) {
    ctx.fillText(line, cardX + 48, curY)
    curY += 92
  }
  ctx.restore()

  // 6. Subtitle
  if (cover.subtitle) {
    curY += 15
    ctx.font = '600 36px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = '#cbd5e1'
    const subLines = wrapText(ctx, cover.subtitle, cardW - 96)
    for (const sline of subLines.slice(0, 2)) {
      ctx.fillText(sline, cardX + 48, curY)
      curY += 52
    }
  }

  // Hook quotation banner
  if (cover.hook) {
    curY += 20
    const hookH = 118
    drawRoundedRect(ctx, cardX + 48, curY, cardW - 96, hookH, 20)
    ctx.fillStyle = 'rgba(234, 179, 8, 0.14)'
    ctx.fill()
    ctx.lineWidth = 1.5
    ctx.strokeStyle = 'rgba(234, 179, 8, 0.35)'
    ctx.stroke()

    ctx.font = '500 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = '#fef08a'
    const hookLines = wrapText(ctx, `“${cover.hook}”`, cardW - 136)
    let hy = curY + 48
    for (const hl of hookLines.slice(0, 2)) {
      ctx.fillText(hl, cardX + 68, hy)
      hy += 40
    }
  }

  // 7. Tags Pills
  const tagY = cardY + cardH - 96
  if (cover.tags && cover.tags.length) {
    let tagX = cardX + 48
    ctx.font = 'bold 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    for (const tag of cover.tags.slice(0, 3)) {
      const tw = ctx.measureText(tag).width + 36
      if (tagX + tw < cardX + cardW - 48) {
        drawRoundedRect(ctx, tagX, tagY, tw, 52, 26)
        ctx.fillStyle = 'rgba(255, 255, 255, 0.12)'
        ctx.fill()
        ctx.lineWidth = 1.5
        ctx.strokeStyle = '#38bdf8'
        ctx.stroke()
        ctx.fillStyle = '#7dd3fc'
        ctx.fillText(tag, tagX + 18, tagY + 36)
        tagX += tw + 16
      }
    }
  }

  // 8. Bottom Swipe Prompt Banner
  ctx.save()
  drawRoundedRect(ctx, 120, 1340, 840, 64, 32)
  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)'
  ctx.fill()
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
  ctx.lineWidth = 1.5
  ctx.stroke()

  ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = '#f8fafc'
  ctx.textAlign = 'center'
  ctx.fillText('滑动翻阅完整拆解卡片', 540, 1382)
  ctx.restore()

  // 5. Global Footer (Page Counter)
  ctx.save()
  ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = '#94a3b8'
  ctx.textAlign = 'right'
  ctx.fillText(`${curPage} / ${totPage}`, 1080 - 60 - 50, 1440 - 60 - 80)
  ctx.restore()

  return canvas
}

/**
 * Renders an official Xiaohongshu 3:4 card (1080 x 1440)
 */
export function renderXhsCardToCanvas(
  card: XhsCardData,
  themeKey: VisualTheme = 'dark_gold',
  brandName = '个人认知 IP 引擎',
  curPage = 1,
  totPage = 1
): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1440
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas

  const t = THEMES[themeKey]

  // 1. Background Gradient
  const grad = ctx.createLinearGradient(0, 0, 1080, 1440)
  grad.addColorStop(0, t.bgStart)
  grad.addColorStop(1, t.bgEnd)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 1080, 1440)

  // Decorative ambient circles
  ctx.save()
  ctx.beginPath()
  ctx.arc(950, 150, 260, 0, Math.PI * 2)
  ctx.fillStyle = themeKey === 'clean_minimal' ? 'rgba(37,99,235,0.06)' : 'rgba(234,179,8,0.08)'
  ctx.fill()
  ctx.beginPath()
  ctx.arc(120, 1300, 320, 0, Math.PI * 2)
  ctx.fillStyle = themeKey === 'clean_minimal' ? 'rgba(79,70,229,0.05)' : 'rgba(168,85,247,0.12)'
  ctx.fill()
  ctx.restore()

  // 2. Inner Frame Card
  const pad = 60
  const innerW = 1080 - pad * 2
  const innerH = 1440 - pad * 2
  drawRoundedRect(ctx, pad, pad, innerW, innerH, 44)
  ctx.fillStyle = t.cardBg
  ctx.fill()
  ctx.lineWidth = 3
  ctx.strokeStyle = t.cardBorder
  ctx.stroke()

  // 3. Header Bar (Brand + Category)
  ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", sans-serif'
  ctx.fillStyle = t.secondaryText
  ctx.fillText(card.author || brandName, pad + 50, pad + 80)

  // Badge pill (Right)
  const badgeText = card.badge || (card.card_type === 'cover' ? '深度干货 · 爆款首图' : `PAGE ${card.index || '01'}`)
  ctx.font = 'bold 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  const badgeMetrics = ctx.measureText(badgeText)
  const badgeW = badgeMetrics.width + 40
  const badgeX = pad + innerW - 50 - badgeW
  drawRoundedRect(ctx, badgeX, pad + 52, badgeW, 44, 22)
  ctx.fillStyle = t.tagBg
  ctx.fill()
  ctx.lineWidth = 1.5
  ctx.strokeStyle = t.cardBorder
  ctx.stroke()
  ctx.fillStyle = t.tagText
  ctx.fillText(badgeText, badgeX + 20, pad + 83)

  // Divider line
  ctx.beginPath()
  ctx.moveTo(pad + 50, pad + 125)
  ctx.lineTo(pad + innerW - 50, pad + 125)
  ctx.strokeStyle = t.cardBorder
  ctx.lineWidth = 1.5
  ctx.stroke()

  // 4. Content by Card Type
  if (card.card_type === 'cover') {
    // COVER CARD
    // Super bold main title (70px)
    ctx.font = '900 70px -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", sans-serif'
    ctx.fillStyle = t.primaryText
    const titleLines = wrapText(ctx, card.title || '核心干货复盘', innerW - 100)
    let curY = pad + 320
    for (const line of titleLines.slice(0, 4)) {
      ctx.fillText(line, pad + 50, curY)
      curY += 92
    }

    // Subtitle
    if (card.subtitle) {
      curY += 26
      ctx.font = '500 36px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.secondaryText
      const subLines = wrapText(ctx, card.subtitle, innerW - 100)
      for (const sline of subLines.slice(0, 2)) {
        ctx.fillText(sline, pad + 50, curY)
        curY += 56
      }
    }

    // Hook Callout Box if present
    if (card.hook) {
      curY += 24
      const hookH = 110
      drawRoundedRect(ctx, pad + 40, curY, innerW - 80, hookH, 20)
      ctx.fillStyle = t.tagBg
      ctx.fill()
      ctx.lineWidth = 1.5
      ctx.strokeStyle = t.cardBorder
      ctx.stroke()

      ctx.font = '500 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.tagText
      const hLines = wrapText(ctx, `“${card.hook}”`, innerW - 140)
      let hy = curY + 46
      for (const hl of hLines.slice(0, 2)) {
        ctx.fillText(hl, pad + 65, hy)
        hy += 40
      }
    }

    // Highlight Tags Pills
    if (card.tags && card.tags.length) {
      let tagX = pad + 50
      const tagY = pad + innerH - 240
      ctx.font = 'bold 30px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      for (const tag of card.tags.slice(0, 3)) {
        const tw = ctx.measureText(tag).width + 44
        if (tagX + tw < pad + innerW - 50) {
          drawRoundedRect(ctx, tagX, tagY, tw, 62, 31)
          ctx.fillStyle = t.tagBg
          ctx.fill()
          ctx.lineWidth = 2
          ctx.strokeStyle = t.accentColor
          ctx.stroke()
          ctx.fillStyle = t.accentColor
          ctx.fillText(tag, tagX + 22, tagY + 43)
          tagX += tw + 20
        }
      }
    }

    // Bottom Swipe Prompt
    ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.secondaryText
    ctx.fillText('滑动翻阅卡片', pad + 50, pad + innerH - 80)

  } else if (card.card_type === 'point') {
    // ═════════════════════════════════════════════════════════════════════════
    // POINT CARD — Two-Phase Dry-Run Measure & Elastic Layout Engine
    // ═════════════════════════════════════════════════════════════════════════
    const stepNum = card.step_number || card.index || '01'
    const contentX = pad + 50
    const contentW = innerW - 100 // 860px usable width

    // Stage Pill & Divider are fixed at top
    // Stage Pill
    drawRoundedRect(ctx, contentX, pad + 175, 170, 52, 26)
    ctx.fillStyle = t.tagBg
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = t.accentColor
    ctx.stroke()

    ctx.font = '900 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.accentColor
    ctx.fillText(`STAGE ${stepNum}`, contentX + 22, pad + 211)

    // PHASE 1: Measure All Elements
    // 1. Title Lines
    ctx.font = '800 46px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    const titleLines = wrapText(ctx, card.title || '核心要点', contentW)
    const titleLineH = 58
    const titleH = titleLines.length * titleLineH

    // 2. Pain Point Analysis (Optional)
    let painH = 0
    let painLines: string[] = []
    const painText = card.pain_point_analysis ? card.pain_point_analysis.trim() : ''
    if (painText) {
      ctx.font = '400 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      painLines = wrapText(ctx, painText, contentW - 170)
      painH = 34 + painLines.length * 30 + 10
    }

    // 3. Key Points (Each with badge + multiple wrapped lines)
    const rawKeyPoints = (card.key_points || []).map(p => p.trim()).filter(Boolean)
    const ptItems: { badge: string; lines: string[]; height: number }[] = []
    ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    for (let i = 0; i < rawKeyPoints.length; i++) {
      const pLines = wrapText(ctx, rawKeyPoints[i], contentW - 75)
      const itemH = Math.max(48, pLines.length * 38 + 6)
      ptItems.push({
        badge: String(i + 1).padStart(2, '0'),
        lines: pLines,
        height: itemH,
      })
    }
    const totalPtsH = ptItems.reduce((acc, it) => acc + it.height, 0)

    // 4. Highlight / Golden Insight Callout (Optional)
    let hlH = 0
    let hlLines: string[] = []
    const hlText = card.highlight ? card.highlight.trim() : ''
    if (hlText) {
      ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      hlLines = wrapText(ctx, `“${hlText}”`, contentW - 50)
      hlH = 56 + hlLines.length * 36 + 18
    }

    // Available vertical space for content between Stage Pill (pad + 245) and Swipe Prompt (pad + innerH - 100)
    const startY = pad + 250
    const bottomLimitY = pad + innerH - 100
    const availableH = bottomLimitY - startY

    // Count blocks: Title + (Pain if any) + Points + (Highlight if any)
    const blockCount = 1 + (painH > 0 ? 1 : 0) + (ptItems.length > 0 ? 1 : 0) + (hlH > 0 ? 1 : 0)
    const pureContentH = titleH + painH + totalPtsH + hlH
    const itemSpacingCount = Math.max(1, ptItems.length - 1)
    const totalGapsNeeded = (blockCount - 1) + (ptItems.length > 1 ? itemSpacingCount * 0.4 : 0)

    // Elastic gap calculation: allows natural vertical expansion when content is compact
    const rawGap = totalGapsNeeded > 0 ? (availableH - pureContentH) / totalGapsNeeded : 36
    const clampedGap = Math.max(16, Math.min(65, rawGap))
    const itemGap = Math.max(12, clampedGap * 0.45)
    
    // If still have extra vertical space, offset startY downwards to center visually
    const totalRenderedH = pureContentH + (blockCount - 1) * clampedGap + (ptItems.length > 1 ? itemSpacingCount * itemGap : 0)
    const extraSpace = availableH - totalRenderedH
    const visualOffsetY = extraSpace > 30 ? Math.min(60, extraSpace * 0.35) : 0

    // PHASE 2: Sequential Rendering (100% Collision-Proof Cascade)
    let curY = startY + visualOffsetY

    // Render Title
    ctx.font = '800 46px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.primaryText
    for (const l of titleLines) {
      ctx.fillText(l, contentX, curY + 40)
      curY += titleLineH
    }

    // Render Pain Point Banner
    if (painH > 0) {
      curY += clampedGap
      drawRoundedRect(ctx, contentX, curY, contentW, painH, 18)
      ctx.fillStyle = 'rgba(239, 68, 68, 0.12)'
      ctx.fill()
      ctx.lineWidth = 1.5
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)'
      ctx.stroke()

      ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = '#f87171'
      ctx.fillText('⚠️ 痛点剖析', contentX + 20, curY + 34)

      ctx.font = '400 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.primaryText
      let py = curY + 34
      for (const pl of painLines) {
        ctx.fillText(pl, contentX + 160, py)
        py += 30
      }
      curY += painH
    }

    // Render Key Points
    if (ptItems.length > 0) {
      curY += clampedGap
      for (let i = 0; i < ptItems.length; i++) {
        const item = ptItems[i]
        // Badge (01, 02...)
        drawRoundedRect(ctx, contentX, curY, 44, 44, 22)
        ctx.fillStyle = t.tagBg
        ctx.fill()
        ctx.lineWidth = 2
        ctx.strokeStyle = t.accentColor
        ctx.stroke()

        ctx.font = '900 20px -apple-system, BlinkMacSystemFont, sans-serif'
        ctx.fillStyle = t.accentColor
        ctx.fillText(item.badge, contentX + 11, curY + 29)

        // Point Content Lines
        ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
        ctx.fillStyle = t.primaryText
        let lineY = curY + 30
        for (const pl of item.lines) {
          ctx.fillText(pl, contentX + 62, lineY)
          lineY += 38
        }
        curY += item.height + (i < ptItems.length - 1 ? itemGap : 0)
      }
    }

    // Render Highlight Callout Box
    if (hlH > 0) {
      curY += clampedGap
      drawRoundedRect(ctx, contentX, curY, contentW, hlH, 20)
      ctx.fillStyle = t.tagBg
      ctx.fill()
      ctx.lineWidth = 2
      ctx.strokeStyle = t.cardBorder
      ctx.stroke()

      ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.goldColor
      ctx.fillText('💡 核心洞察', contentX + 24, curY + 38)

      ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.primaryText
      let qY = curY + 76
      for (const ql of hlLines) {
        ctx.fillText(ql, contentX + 24, qY)
        qY += 36
      }
      curY += hlH
    }

  } else {
    // ═════════════════════════════════════════════════════════════════════════
    // SUMMARY CARD — Two-Phase Dry-Run Measure & Elastic Layout Engine
    // ═════════════════════════════════════════════════════════════════════════
    const contentX = pad + 50
    const contentW = innerW - 100 // 860px usable width

    // PHASE 1: Measure All Summary Elements
    // 1. Title Lines
    ctx.font = '900 50px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    const titleLines = wrapText(ctx, card.title || '破局认知与行动复盘', contentW)
    const titleLineH = 64
    const titleH = titleLines.length * titleLineH

    // 2. Golden Quote Box (Optional)
    let gH = 0
    let gLines: string[] = []
    const gQuote = card.golden_quote ? card.golden_quote.trim() : ''
    if (gQuote) {
      ctx.font = '600 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      gLines = wrapText(ctx, `“${gQuote}”`, contentW - 48)
      gH = 50 + gLines.length * 40 + 18
    }

    // 3. Action Checklist Items
    const rawChecklist = (card.checklist && card.checklist.length > 0)
      ? card.checklist
      : [
          '破除思维定势，抓住关键认知杠杆',
          '减少低效内耗，建立正向反馈闭环',
          '持续小步快跑，在实战中敏捷迭代',
        ]
    const ckItems: { lines: string[]; height: number }[] = []
    ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    for (const item of rawChecklist) {
      const cLines = wrapText(ctx, item.trim(), contentW - 48)
      const itemH = Math.max(38, cLines.length * 36)
      ckItems.push({ lines: cLines, height: itemH })
    }
    const ckHeaderH = 34
    const totalCkItemsH = ckItems.reduce((acc, it) => acc + it.height, 0)
    const checklistH = ckHeaderH + totalCkItemsH

    // 4. Interaction Prompt Box (Optional)
    let ipH = 0
    let ipLines: string[] = []
    const ipText = card.interaction_prompt ? card.interaction_prompt.trim() : ''
    if (ipText) {
      ctx.font = '600 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ipLines = wrapText(ctx, ipText, contentW - 44)
      ipH = 28 + ipLines.length * 28 + 14
    }

    // 5. CTA Bottom Bar
    const ctaText = card.cta ? card.cta.trim() : '点赞 + 收藏，持续沉淀你的 Thinking DNA 🧠'
    ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    const ctaLines = wrapText(ctx, ctaText, contentW - 44)
    const ctaH = 32 + ctaLines.length * 32 + 14

    // Available vertical space for content between pad + 175 and Footer top (pad + innerH - 140)
    // Reserving 140px ensures CTA bar never touches the bottom page counter (7 / 7)
    const startY = pad + 175
    const bottomLimitY = pad + innerH - 140
    const availableH = bottomLimitY - startY

    // Count blocks: Title + (Quote if any) + Checklist + (Prompt if any) + CTA
    const blockCount = 1 + (gH > 0 ? 1 : 0) + 1 + (ipH > 0 ? 1 : 0) + 1
    const pureContentH = titleH + gH + checklistH + ipH + ctaH
    const itemSpacingCount = Math.max(1, ckItems.length - 1)
    const totalGapsNeeded = (blockCount - 1) + (ckItems.length > 1 ? itemSpacingCount * 0.35 : 0)

    // Elastic gap calculation: allows natural vertical expansion when content is compact
    const rawGap = totalGapsNeeded > 0 ? (availableH - pureContentH) / totalGapsNeeded : 32
    const clampedGap = Math.max(16, Math.min(54, rawGap))
    const ckItemGap = Math.max(8, clampedGap * 0.35)

    // Visual centering: distribute remaining space gracefully if content is very compact
    const totalRenderedH = pureContentH + (blockCount - 1) * clampedGap + (ckItems.length > 1 ? itemSpacingCount * ckItemGap : 0)
    const extraSpace = availableH - totalRenderedH
    const visualOffsetY = extraSpace > 20 ? Math.min(45, extraSpace * 0.3) : 0

    // PHASE 2: Sequential Rendering (100% Collision-Proof Cascade)
    let curY = startY + visualOffsetY

    // Render Title
    ctx.font = '900 50px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.primaryText
    for (const l of titleLines) {
      ctx.fillText(l, contentX, curY + 44)
      curY += titleLineH
    }

    // Thin divider line under title
    curY += 14
    ctx.beginPath()
    ctx.moveTo(contentX, curY)
    ctx.lineTo(contentX + contentW, curY)
    ctx.strokeStyle = t.cardBorder
    ctx.lineWidth = 1.5
    ctx.stroke()
    curY += 14

    // Render Golden Quote Box
    if (gH > 0) {
      curY += clampedGap
      drawRoundedRect(ctx, contentX, curY, contentW, gH, 22)
      ctx.fillStyle = t.tagBg
      ctx.fill()
      ctx.lineWidth = 2
      ctx.strokeStyle = t.cardBorder
      ctx.stroke()

      ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.goldColor
      ctx.fillText('🏆 高光金句', contentX + 24, curY + 36)

      ctx.font = '600 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.primaryText
      let gy = curY + 76
      for (const gl of gLines) {
        ctx.fillText(gl, contentX + 24, gy)
        gy += 40
      }
      curY += gH
    }

    // Render Action Checklist
    curY += clampedGap
    ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.accentColor
    ctx.fillText('🎯 落地实操清单', contentX, curY + 26)
    curY += ckHeaderH + 10

    for (let i = 0; i < ckItems.length; i++) {
      const it = ckItems[i]
      ctx.font = 'bold 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.goldColor
      ctx.fillText('✓', contentX, curY + 26)

      ctx.font = '500 26px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      ctx.fillStyle = t.primaryText
      let lineY = curY + 26
      for (const il of it.lines) {
        ctx.fillText(il, contentX + 38, lineY)
        lineY += 36
      }
      curY += it.height + (i < ckItems.length - 1 ? ckItemGap : 0)
    }

    // Render Interaction Prompt Box
    if (ipH > 0) {
      curY += clampedGap
      drawRoundedRect(ctx, contentX, curY, contentW, ipH, 16)
      ctx.fillStyle = 'rgba(56, 189, 248, 0.12)'
      ctx.fill()
      ctx.lineWidth = 1.5
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)'
      ctx.stroke()

      ctx.fillStyle = '#38bdf8'
      ctx.font = '600 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
      let ipLineY = curY + 28
      for (const ipl of ipLines) {
        ctx.fillText(ipl, contentX + 20, ipLineY)
        ipLineY += 28
      }
      curY += ipH
    }

    // Render CTA Bottom Bar
    curY += clampedGap
    drawRoundedRect(ctx, contentX, curY, contentW, ctaH, 20)
    ctx.fillStyle = t.tagBg
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = t.accentColor
    ctx.stroke()

    ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.accentColor
    let ctaLineY = curY + 34
    for (const cl of ctaLines) {
      ctx.fillText(cl, contentX + 20, ctaLineY)
      ctaLineY += 32
    }
  }

  // 5. Global Footer (Page Counter)
  ctx.save()
  ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = t.secondaryText
  ctx.textAlign = 'right'
  ctx.fillText(`${curPage} / ${totPage}`, pad + innerW - 50, pad + innerH - 80)
  ctx.restore()

  return canvas
}
