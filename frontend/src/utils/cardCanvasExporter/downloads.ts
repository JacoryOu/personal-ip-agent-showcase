// Browser download helpers.

/**
 * Helper to download canvas directly as a PNG file in browser
 */
export function downloadCanvasAsPng(canvas: HTMLCanvasElement, filename: string): void {
  const dataUrl = canvas.toDataURL('image/png')
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename.endsWith('.png') ? filename : `${filename}.png`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/**
 * Helper to download an image from a URL or data URL directly
 */
export function downloadImageFromUrl(url: string, filename: string): void {
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.png') || filename.endsWith('.svg') || filename.endsWith('.jpg') ? filename : `${filename}.png`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
