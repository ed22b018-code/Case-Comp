import { toPng } from 'html-to-image'

// ── PNG capture ───────────────────────────────────────────────────────────────

export async function captureAsPng(el: HTMLElement, filename: string): Promise<void> {
  const dataUrl = await toPng(el, { cacheBust: true, pixelRatio: 2 })
  trigger(dataUrl, filename)
}

// ── Native SVG extraction (Recharts charts only — pure SVG elements) ──────────

export function extractSvgFromContainer(container: HTMLElement, filename: string): void {
  const svgEl = container.querySelector('svg')
  if (!svgEl) { console.warn('[export] No SVG element found in container'); return }

  // Inline computed styles so the SVG renders standalone (outside the app's CSS)
  const clone = svgEl.cloneNode(true) as SVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  // Preserve explicit width/height from the computed size
  const rect = svgEl.getBoundingClientRect()
  clone.setAttribute('width', String(Math.round(rect.width)))
  clone.setAttribute('height', String(Math.round(rect.height)))

  const serializer = new XMLSerializer()
  const svgStr = serializer.serializeToString(clone)
  const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
  trigger(URL.createObjectURL(blob), filename, true)
}

// ── CSV download ──────────────────────────────────────────────────────────────

export function downloadCsv(rows: Record<string, unknown>[], filename: string): void {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const escape = (v: unknown) => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  const csv = [
    headers.join(','),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(',')),
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  trigger(URL.createObjectURL(blob), filename, true)
}

// ── Shared helper ─────────────────────────────────────────────────────────────

function trigger(href: string, filename: string, revoke = false): void {
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  if (revoke) setTimeout(() => URL.revokeObjectURL(href), 5000)
}
