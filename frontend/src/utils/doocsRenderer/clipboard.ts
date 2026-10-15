// doocs/md layout & style rendering engine for WeChat Official Accounts.
// See the original module docblock in ../../../utils/doocsRenderer.ts for the full
// feature overview of the Markdown-to-WeChat-HTML compiler.

/**
 * Robust cross-browser HTML and plain text copy to clipboard
 */
export async function copyDoocsHtmlToClipboard(html: string, plainText?: string): Promise<boolean> {
  const text = plainText || html.replace(/<[^>]+>/g, '').trim()

  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard && typeof ClipboardItem !== 'undefined') {
      const htmlBlob = new Blob([html], { type: 'text/html' })
      const textBlob = new Blob([text], { type: 'text/plain' })
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': htmlBlob,
          'text/plain': textBlob,
        }),
      ])
      return true
    }
  } catch (err) {
    console.warn('ClipboardItem API write failed, trying DOM selection fallback...', err)
  }

  try {
    if (typeof document !== 'undefined') {
      const container = document.createElement('div')
      container.innerHTML = html
      container.style.position = 'fixed'
      container.style.pointerEvents = 'none'
      container.style.opacity = '0'
      container.style.left = '-9999px'
      document.body.appendChild(container)

      const range = document.createRange()
      range.selectNodeContents(container)
      const selection = window.getSelection()
      if (selection) {
        selection.removeAllRanges()
        selection.addRange(range)
        const success = document.execCommand('copy')
        selection.removeAllRanges()
        document.body.removeChild(container)
        if (success) return true
      }
    }
  } catch (err) {
    console.error('DOM selection copy fallback failed', err)
  }

  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (err) {
    console.error('Failed to copy to clipboard', err)
  }
  return false
}

/**
 * Copies a single image to clipboard as PNG blob
 */
export async function copySingleImageToClipboard(imageUrl: string): Promise<boolean> {
  try {
    if (typeof window === 'undefined') return false

    const img = new Image()
    if (imageUrl.startsWith('http')) {
      img.crossOrigin = 'anonymous'
    }

    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = (e) => reject(e)
      img.src = imageUrl
    })

    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth || img.width || 800
    canvas.height = img.naturalHeight || img.height || 450
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Could not get canvas 2D context')

    ctx.drawImage(img, 0, 0)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), 'image/png')
    })

    if (!blob) throw new Error('Failed to create PNG blob from canvas')

    if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob }),
      ])
      return true
    }
  } catch (err) {
    console.error('Failed to copy image to clipboard:', err)
  }
  return false
}
