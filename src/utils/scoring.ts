import type { DistrictScore, Therapy, ViewMode, Pillar, PillarScores } from '../types/district'
import { THERAPIES, PILLARS } from '../types/district'

export function getDisplayValue(
  district: DistrictScore,
  therapy: Therapy,
  view: ViewMode,
): number {
  const s = district.scores[therapy]
  if (view === 'current') return s.current
  if (view === 'future') return s.future
  return s.future - s.current
}

export function computeRanks(
  districts: DistrictScore[],
  therapy: Therapy,
): Map<string, number> {
  const sorted = [...districts].sort(
    (a, b) => b.scores[therapy].current - a.scores[therapy].current,
  )
  const ranks = new Map<string, number>()
  sorted.forEach((d, i) => ranks.set(d.districtId, i + 1))
  return ranks
}

export function computeMedians(
  districts: DistrictScore[],
  _weights: Record<Therapy, PillarScores>,
): Record<Therapy, PillarScores> {
  const medians = {} as Record<Therapy, PillarScores>
  for (const therapy of THERAPIES) {
    const raw: Record<Pillar, number[]> = {
      demand: [], monetization: [], access: [], growth: [],
    }
    for (const d of districts) {
      for (const p of PILLARS) {
        raw[p].push(d.pillars[therapy][p])
      }
    }
    medians[therapy] = {} as PillarScores
    for (const p of PILLARS) {
      const sorted = raw[p].slice().sort((a, b) => a - b)
      const mid = Math.floor(sorted.length / 2)
      medians[therapy][p] =
        sorted.length % 2 === 0
          ? (sorted[mid - 1] + sorted[mid]) / 2
          : sorted[mid]
    }
  }
  return medians
}

// Returns raw 0-100 pillar scores (M2: pillars are already standalone 0-100, no division needed)
export function getPillarRawScores(
  district: DistrictScore,
  therapy: Therapy,
  _weights: Record<Therapy, PillarScores>,
): PillarScores {
  return { ...district.pillars[therapy] }
}

export function getDomain(
  districts: DistrictScore[],
  therapy: Therapy,
  view: ViewMode,
): [number, number] {
  if (view === 'current' || view === 'future') return [0, 100]
  const values = districts.map((d) => getDisplayValue(d, therapy, view))
  return [Math.min(...values), Math.max(...values)]
}
