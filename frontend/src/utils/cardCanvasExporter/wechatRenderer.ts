// WeChat renderers (official account cover + 16:9 quote card).

import type { WechatCoverData, WechatQuoteData, VisualTheme } from './types'
import { THEMES } from './themes'
import { wrapText, drawRoundedRect } from './canvasHelpers'

/**
 * Renders an official WeChat Official Account Cover (900 x 383)
 */
export function renderWechatCoverToCanvas(
  cover: WechatCoverData,
  themeKey: VisualTheme = 'dark_gold'
): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = 900
  canvas.height = 383
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas

  const t = THEMES[themeKey]

  const grad = ctx.createLinearGradient(0, 0, 900, 383)
  grad.addColorStop(0, t.bgStart)
  grad.addColorStop(1, t.bgEnd)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 900, 383)

  // Ambient glow
  ctx.save()
  ctx.beginPath()
  ctx.arc(800, 100, 200, 0, Math.PI * 2)
  ctx.fillStyle = themeKey === 'clean_minimal' ? 'rgba(37,99,235,0.08)' : 'rgba(234,179,8,0.1)'
  ctx.fill()
  ctx.restore()

  // Inner border card
  const pad = 24
  drawRoundedRect(ctx, pad, pad, 900 - pad * 2, 383 - pad * 2, 20)
  ctx.fillStyle = t.cardBg
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = t.cardBorder
  ctx.stroke()

  // Badge Tag
  const badgeText = cover.badge || '深度干货'
  ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  const bw = ctx.measureText(badgeText).width + 24
  drawRoundedRect(ctx, pad + 32, pad + 32, bw, 32, 16)
  ctx.fillStyle = t.tagBg
  ctx.fill()
  ctx.fillStyle = t.tagText
  ctx.fillText(badgeText, pad + 44, pad + 54)

  // Author on right
  ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = t.secondaryText
  ctx.fillText(cover.author || '个人认知 IP 引擎', 900 - pad - 190, pad + 54)

  // Headline Title
  ctx.font = '900 44px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = t.primaryText
  const lines = wrapText(ctx, cover.title, 900 - pad * 2 - 64)
  let curY = pad + 140
  for (const line of lines.slice(0, 2)) {
    ctx.fillText(line, pad + 32, curY)
    curY += 58
  }

  // Subtitle
  if (cover.subtitle) {
    ctx.font = '500 22px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
    ctx.fillStyle = t.secondaryText
    ctx.fillText(cover.subtitle, pad + 32, curY + 16)
  }

  // Bottom standard ratio indicator
  ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, sans-serif'
  ctx.fillStyle = t.accentColor
  ctx.fillText('WECHAT OFFICIAL 900 ? 383 HD', pad + 32, 383 - pad - 20)

  return canvas
}

/**
 * Renders a 16:9 Quote Card (1200 x 675)
 */
export function renderWechatQuoteToCanvas(
  quoteData: WechatQuoteData,
  themeKey: VisualTheme = 'dark_gold'
): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = 1200
  canvas.height = 675
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas

  const t = THEMES[themeKey]

  const grad = ctx.createLinearGradient(0, 0, 1200, 675)
  grad.addColorStop(0, t.bgStart)
  grad.addColorStop(1, t.bgEnd)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 1200, 675)

  const pad = 40
  drawRoundedRect(ctx, pad, pad, 1200 - pad * 2, 675 - pad * 2, 28)
  ctx.fillStyle = t.cardBg
  ctx.fill()
  ctx.lineWidth = 2.5
  ctx.strokeStyle = t.cardBorder
  ctx.stroke()

  // Quote Icon
  ctx.font = '900 120px Georgia, serif'
  ctx.fillStyle = t.accentColor
  ctx.fillText('?', pad + 50, pad + 150)

  // Quote Content
  ctx.font = '600 42px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = t.primaryText
  const qLines = wrapText(ctx, quoteData.quote, 1200 - pad * 2 - 120)
  let qY = pad + 240
  for (const ql of qLines.slice(0, 4)) {
    ctx.fillText(ql, pad + 60, qY)
    qY += 64
  }

  // Source & Attribution
  ctx.font = '500 24px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif'
  ctx.fillStyle = t.secondaryText
  ctx.fillText(`—— 节选自《${quoteData.source}》 ${quoteData.author}`, pad + 60, 675 - pad - 50)

  return canvas
}
