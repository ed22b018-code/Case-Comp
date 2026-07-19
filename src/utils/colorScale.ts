import type { ViewMode } from '../types/district'

interface ColorStop {
  pos: number  // 0..1
  r: number; g: number; b: number
}

function hex(h: string): ColorStop['r'] extends number ? [number,number,number] : never {
  const v = parseInt(h.replace('#', ''), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255] as unknown as ReturnType<typeof hex>
}

function stops(hexColors: string[]): ColorStop[] {
  return hexColors.map((h, i) => {
    const [r, g, b] = hex(h) as unknown as [number, number, number]
    return { pos: i / (hexColors.length - 1), r, g, b }
  })
}

// YlOrRd sequential — light cream → deep red
const SEQUENTIAL: ColorStop[] = stops([
  '#FFFFD4', '#FED98E', '#FE9929', '#D95F0E', '#993404',
])

// RdGy diverging — red ↔ neutral grey ↔ green
const DIVERGING: ColorStop[] = stops([
  '#D73027', '#FC8D59', '#FEE08B', '#F7F7F7', '#D9EF8B', '#91CF60', '#1A9850',
])

export const NO_DATA_COLOR = '#E5E7EB'
export const HOVER_COLOR = '#0F172A'
export const SELECTED_BORDER = '#1D4ED8'

// Categorical palette for 8 cluster archetypes
export const CLUSTER_COLORS = [
  '#E57200', // 0 Emerging Opportunity — Sun Pharma orange
  '#1D4ED8', // 1 High Access Low Monetisation — blue
  '#16A34A', // 2 Premium Urban — green
  '#DC2626', // 3 Chronic-Driven Growth — red
  '#7C3AED', // 4 Underserved Potential — purple
  '#0891B2', // 5 Balanced Mid-Tier — cyan
  '#B45309', // 6 Acute-Demand Hub — amber
  '#64748B', // 7 Infrastructure-Deficit — slate
]

export function clusterColor(label: number | undefined): string {
  if (label === undefined || label === null || label < 0) return NO_DATA_COLOR
  return CLUSTER_COLORS[label % CLUSTER_COLORS.length]
}

function interpolate(colorStops: ColorStop[], t: number): string {
  const clamped = Math.max(0, Math.min(1, t))
  for (let i = 0; i < colorStops.length - 1; i++) {
    const lo = colorStops[i], hi = colorStops[i + 1]
    if (clamped >= lo.pos && clamped <= hi.pos) {
      const local = (clamped - lo.pos) / (hi.pos - lo.pos)
      const r = Math.round(lo.r + (hi.r - lo.r) * local)
      const g = Math.round(lo.g + (hi.g - lo.g) * local)
      const b = Math.round(lo.b + (hi.b - lo.b) * local)
      return `rgb(${r},${g},${b})`
    }
  }
  return `rgb(${colorStops[colorStops.length - 1].r},${colorStops[colorStops.length - 1].g},${colorStops[colorStops.length - 1].b})`
}

export function valueToColor(
  value: number,
  domain: [number, number],
  view: ViewMode,
): string {
  const [lo, hi] = domain
  if (hi === lo) return interpolate(SEQUENTIAL, 0.5)
  const t = (value - lo) / (hi - lo)

  if (view === 'growth') {
    // Centre diverging scale at 0
    const absMax = Math.max(Math.abs(lo), Math.abs(hi))
    const tDiv = absMax > 0 ? (value + absMax) / (2 * absMax) : 0.5
    return interpolate(DIVERGING, tDiv)
  }
  return interpolate(SEQUENTIAL, t)
}

// Returns ordered legend stops for rendering
export function legendStops(view: ViewMode, domain: [number, number]): Array<{ color: string; label: string }> {
  const scale = view === 'growth' ? DIVERGING : SEQUENTIAL
  const [lo, hi] = domain
  const steps = 5
  return Array.from({ length: steps }, (_, i) => {
    const t = i / (steps - 1)
    const value = lo + (hi - lo) * t
    const color = interpolate(scale, view === 'growth'
      ? (() => { const absMax = Math.max(Math.abs(lo), Math.abs(hi)); return absMax > 0 ? (value + absMax) / (2 * absMax) : 0.5 })()
      : t)
    const label = view === 'growth'
      ? (value >= 0 ? `+${value.toFixed(1)}` : value.toFixed(1))
      : value.toFixed(0)
    return { color, label }
  })
}
