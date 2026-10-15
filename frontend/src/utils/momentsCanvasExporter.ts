/**
 * 1:1 Canvas Exporter for WeChat Moments Visual Cards (1080x1080px)
 * Clean aesthetic style: warm cream/white background, elegant serif title,
 * takeaway points, persona badge, tags, and copyright seal.
 */

export interface MomentsCanvasData {
  category: string
  topic: string
  personaName?: string
  salutation?: string
  productName?: string
  productCoverImage?: string
  lines: string[]
  hook?: string
  tags?: string[]
  theme?: 'cream_minimal' | 'tea_amber' | 'zen_mist'
}

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    if (!src) {
      resolve(null)
      return
    }
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => {
      const fallback = new Image()
      fallback.onload = () => resolve(fallback)
      fallback.onerror = () => resolve(null)
      fallback.src = src
    }
    img.src = src
    setTimeout(() => resolve(null), 3500)
  })
}

interface CanvasTheme {
  bgStart: string
  bgEnd: string
  cardBg: string
  border: string
  titleColor: string
  bodyColor: string
  accentColor: string
  tagBg: string
  tagText: string
  bannerBg: string
  bannerText: string
}

const THEMES: Record<string, CanvasTheme> = {
  cream_minimal: {
    bgStart: '#FAF7F2',
    bgEnd: '#F2ECE4',
    cardBg: '#FFFFFF',
    border: '#E8DED1',
    titleColor: '#2C2724',
    bodyColor: '#4A433E',
    accentColor: '#8C7051',
    tagBg: '#F3EDE4',
    tagText: '#7B6349',
    bannerBg: '#F5EEE6',
    bannerText: '#6D5339',
  },
  tea_amber: {
    bgStart: '#FDFBF7',
    bgEnd: '#F5EFE6',
    cardBg: '#FFFFFF',
    border: '#E3D3C1',
    titleColor: '#2B231D',
    bodyColor: '#473A31',
    accentColor: '#A86C3E',
    tagBg: '#EFE5D8',
    tagText: '#87532A',
    bannerBg: '#F7EDE1',
    bannerText: '#7D4720',
  },
  zen_mist: {
    bgStart: '#F6F8F6',
    bgEnd: '#EBEFEA',
    cardBg: '#FFFFFF',
    border: '#D5DFD4',
    titleColor: '#1F2A22',
    bodyColor: '#3A483E',
    accentColor: '#4D7C5D',
    tagBg: '#E2EBE1',
    tagText: '#3B6348',
    bannerBg: '#E9F1E8',
    bannerText: '#345B41',
  },
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
): string[] {
  const lines: string[] = []
  const paragraphs = text.split('\n')

  for (const para of paragraphs) {
    if (!para.trim()) continue
    let currentLine = ''
    for (const char of para) {
      const testLine = currentLine + char
      const metrics = ctx.measureText(testLine)
      if (metrics.width > maxWidth && currentLine.length > 0) {
        lines.push(currentLine)
        currentLine = char
      } else {
        currentLine = testLine
      }
    }
    if (currentLine) {
      lines.push(currentLine)
    }
  }

  return lines
}

export async function renderMomentsCanvas(
  canvas: HTMLCanvasElement,
  data: MomentsCanvasData
): Promise<void> {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = 1080
  const height = 1080
  canvas.width = width
  canvas.height = height

  const themeKey = data.theme || 'cream_minimal'
  const t = THEMES[themeKey] || THEMES.cream_minimal

  // 1. Background Gradient
  const grad = ctx.createLinearGradient(0, 0, width, height)
  grad.addColorStop(0, t.bgStart)
  grad.addColorStop(1, t.bgEnd)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, width, height)

  // 2. Outer decorative frame & inner card
  const margin = 50
  const cardWidth = width - margin * 2
  const cardHeight = height - margin * 2

  // Soft shadow
  ctx.save()
  ctx.shadowColor = 'rgba(74, 69, 62, 0.08)'
  ctx.shadowBlur = 30
  ctx.shadowOffsetY = 15
  ctx.fillStyle = t.cardBg
  roundRect(ctx, margin, margin, cardWidth, cardHeight, 28)
  ctx.fill()
  ctx.restore()

  // Elegant inner border
  ctx.strokeStyle = t.border
  ctx.lineWidth = 2
  roundRect(ctx, margin + 14, margin + 14, cardWidth - 28, cardHeight - 28, 20)
  ctx.stroke()

  let currentY = margin + 55

  // 3. Header: Category Pill Badge & Persona Name
  ctx.save()
  const badgeText = `【 ${data.category || '私域手记'} 】`
  ctx.font = 'bold 24px "Noto Serif SC", "Songti SC", SimSun, serif'
  const badgeWidth = ctx.measureText(badgeText).width + 36

  // Badge background
  ctx.fillStyle = t.tagBg
  roundRect(ctx, margin + 40, currentY, badgeWidth, 42, 21)
  ctx.fill()

  // Badge text
  ctx.fillStyle = t.tagText
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(badgeText, margin + 58, currentY + 21)

  // Persona & salutation right-aligned
  if (data.personaName || data.salutation) {
    const authorText = `${data.personaName || '主理人'} · ${data.salutation || '生活随笔'}`
    ctx.font = '22px system-ui, -apple-system, sans-serif'
    ctx.fillStyle = t.accentColor
    ctx.textAlign = 'right'
    ctx.fillText(authorText, width - margin - 45, currentY + 21)
  }
  ctx.restore()

  currentY += 75

  // 4. Topic / Title (Serif prominent)
  ctx.save()
  ctx.font = 'bold 44px "Noto Serif SC", "Songti SC", "Source Han Serif CN", serif'
  ctx.fillStyle = t.titleColor
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'

  const titleLines = wrapText(ctx, data.topic || '日常温和调养手记', cardWidth - 90)
  for (const tLine of titleLines.slice(0, 2)) {
    ctx.fillText(tLine, margin + 45, currentY)
    currentY += 56
  }
  ctx.restore()

  // Decorative divider line
  currentY += 15
  ctx.strokeStyle = t.border
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(margin + 45, currentY)
  ctx.lineTo(width - margin - 45, currentY)
  ctx.stroke()

  currentY += 30

  // 5. Product highlight box or visual image banner if available
  let loadedProductImg: HTMLImageElement | null = null
  if (data.productCoverImage) {
    try {
      loadedProductImg = await loadImage(data.productCoverImage)
    } catch {
      loadedProductImg = null
    }
  }

  if (loadedProductImg) {
    const boxHeight = 120
    const boxWidth = cardWidth - 90
    const boxX = margin + 45
    const boxY = currentY

    ctx.save()
    ctx.fillStyle = t.bannerBg
    roundRect(ctx, boxX, boxY, boxWidth, boxHeight, 16)
    ctx.fill()
    ctx.strokeStyle = t.border
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Thumbnail
    const pad = 10
    const imgSize = boxHeight - pad * 2
    const imgX = boxX + pad
    const imgY = boxY + pad

    ctx.save()
    roundRect(ctx, imgX, imgY, imgSize, imgSize, 12)
    ctx.clip()

    const iw = loadedProductImg.naturalWidth || loadedProductImg.width
    const ih = loadedProductImg.naturalHeight || loadedProductImg.height
    const minDim = Math.min(iw, ih)
    const sx = (iw - minDim) / 2
    const sy = (ih - minDim) / 2
    ctx.drawImage(loadedProductImg, sx, sy, minDim, minDim, imgX, imgY, imgSize, imgSize)
    ctx.restore()

    // Info text
    const textX = imgX + imgSize + 18
    const textMaxW = boxWidth - (imgSize + pad * 2 + 25)

    ctx.fillStyle = t.accentColor
    ctx.font = 'bold 18px system-ui, -apple-system, sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText('🌿 实体好物交付方案', textX, boxY + 16)

    ctx.fillStyle = t.titleColor
    ctx.font = 'bold 24px "Noto Serif SC", "Songti SC", serif'
    const prodNameLines = wrapText(ctx, data.productName || '私域好物', textMaxW)
    ctx.fillText(prodNameLines[0] || '', textX, boxY + 44)

    ctx.fillStyle = t.bodyColor
    ctx.font = '17px system-ui, -apple-system, sans-serif'
    if (prodNameLines.length > 1) {
      ctx.fillText(prodNameLines[1], textX, boxY + 76)
    } else {
      ctx.fillText('真实自用体感 · 匠心选品 · 溯源保障', textX, boxY + 76)
    }

    ctx.restore()
    currentY += boxHeight + 20
  } else if (data.productName) {
    ctx.save()
    ctx.fillStyle = t.bannerBg
    roundRect(ctx, margin + 45, currentY, cardWidth - 90, 56, 14)
    ctx.fill()

    ctx.font = 'bold 22px system-ui, -apple-system, sans-serif'
    ctx.fillStyle = t.accentColor
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(`🌿 实体好物植入：${data.productName}`, margin + 65, currentY + 28)
    ctx.restore()

    currentY += 75
  }

  // 6. Body Content / Key Takeaway Points
  ctx.save()
  ctx.font = '27px system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif'
  ctx.fillStyle = t.bodyColor
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'

  const availableHeight = height - margin - 220 - currentY
  const maxBodyLines = Math.floor(availableHeight / 44)

  const cleanLines = data.lines
    .map(l => l.trim())
    .filter(l => l.length > 0 && !l.startsWith('---'))

  let printedLines = 0
  for (const line of cleanLines) {
    if (printedLines >= maxBodyLines) break
    const wrapped = wrapText(ctx, line, cardWidth - 110)
    for (const wLine of wrapped) {
      if (printedLines >= maxBodyLines) break
      // Draw subtle leaf/bullet icon for top items
      if (printedLines % 2 === 0) {
        ctx.fillStyle = t.accentColor
        ctx.font = '20px system-ui'
        ctx.fillText('•', margin + 45, currentY + 4)
      }
      ctx.fillStyle = t.bodyColor
      ctx.font = '27px system-ui, -apple-system, "PingFang SC", sans-serif'
      ctx.fillText(wLine, margin + 68, currentY)
      currentY += 44
      printedLines++
    }
    currentY += 8
  }
  ctx.restore()

  // 7. Curiosity Hook / Golden Quote Highlight Box (with text wrap)
  if (data.hook) {
    ctx.font = 'bold 22px "Noto Serif SC", "Songti SC", serif'
    const hookLines = wrapText(ctx, `✨ ${data.hook}`, cardWidth - 130)
    const boxHeight = hookLines.length > 1 ? 84 : 64
    currentY = Math.max(currentY + 10, height - margin - 110 - boxHeight)
    ctx.save()
    ctx.fillStyle = t.bannerBg
    roundRect(ctx, margin + 45, currentY, cardWidth - 90, boxHeight, 16)
    ctx.fill()

    ctx.strokeStyle = t.border
    ctx.lineWidth = 1
    roundRect(ctx, margin + 45, currentY, cardWidth - 90, boxHeight, 16)
    ctx.stroke()

    ctx.font = 'bold 22px "Noto Serif SC", "Songti SC", serif'
    ctx.fillStyle = t.bannerText
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    for (let hIdx = 0; hIdx < Math.min(hookLines.length, 2); hIdx++) {
      ctx.fillText(hookLines[hIdx], margin + 65, currentY + 16 + hIdx * 28)
    }
    ctx.restore()
  }

  // 8. Footer: Tags + Author Seal Mark
  const footerY = height - margin - 50
  ctx.save()
  let tagX = margin + 45
  if (data.tags && data.tags.length > 0) {
    ctx.font = '20px system-ui, -apple-system, sans-serif'
    for (const tag of data.tags.slice(0, 4)) {
      const tagText = tag.startsWith('#') ? tag : `#${tag}`
      const tW = ctx.measureText(tagText).width + 24
      ctx.fillStyle = t.tagBg
      roundRect(ctx, tagX, footerY - 14, tW, 34, 8)
      ctx.fill()

      ctx.fillStyle = t.tagText
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillText(tagText, tagX + 12, footerY + 3)
      tagX += tW + 12
    }
  }

  // Copyright / Stamp Seal
  ctx.font = '18px "Noto Serif SC", "Songti SC", serif'
  ctx.fillStyle = t.accentColor
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  ctx.fillText('私域 IP 操盘中枢 · 原创出品', width - margin - 45, footerY + 3)
  ctx.restore()
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
): void {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

export function downloadMomentsCanvas(
  canvas: HTMLCanvasElement,
  filename: string = 'moments-1x1-card.png'
): void {
  const link = document.createElement('a')
  link.download = filename
  link.href = canvas.toDataURL('image/png', 1.0)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export async function copyMomentsCanvasToClipboard(
  canvas: HTMLCanvasElement
): Promise<boolean> {
  return new Promise(resolve => {
    canvas.toBlob(async blob => {
      if (!blob) {
        resolve(false)
        return
      }
      try {
        if (navigator.clipboard && navigator.clipboard.write) {
          const item = new ClipboardItem({ 'image/png': blob })
          await navigator.clipboard.write([item])
          resolve(true)
        } else {
          resolve(false)
        }
      } catch (e) {
        console.warn('Clipboard write failed:', e)
        resolve(false)
      }
    }, 'image/png')
  })
}
