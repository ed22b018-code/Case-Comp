import { useEffect, useState } from 'react'
import type {
  AppData, DistrictScore, MockData, ClusterProfile, Quadrant, Therapy,
} from '../types/district'
import { THERAPIES } from '../types/district'
import { computeRanks, computeMedians } from '../utils/scoring'

function arrMedian(arr: number[]): number {
  if (arr.length === 0) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

function assignQuadrant(
  current: number, growth: number,
  medCurrent: number, medGrowth: number,
): Quadrant {
  const highNow  = current >= medCurrent
  const highGrow = growth  >= medGrowth
  if (highNow  && highGrow)  return 'Stars'
  if (highNow  && !highGrow) return 'Cash Cows'
  if (!highNow && highGrow)  return 'Emerging'
  return 'Low Priority'
}

export function useData(): { data: AppData | null; loading: boolean; error: string | null } {
  const [state, setState] = useState<{
    data: AppData | null; loading: boolean; error: string | null
  }>({ data: null, loading: true, error: null })

  useEffect(() => {
    Promise.all([
      fetch('/data/geo/india_districts.geojson').then((r) => r.json()),
      fetch('/data/scores.json').then((r) => r.json()),
      fetch('/data/clusters.json').then((r) => r.json()).catch(() => ({ k: 0, profiles: [] })),
    ])
      .then(([geo, mock, clustersRaw]: [GeoJSON.FeatureCollection, MockData, { profiles: ClusterProfile[] }]) => {
        const districts: DistrictScore[] = mock.districts

        // ── Compute median current + median growth per therapy (for quadrant thresholds) ──
        const medianCurrent = {} as Record<Therapy, number>
        const medianGrowth  = {} as Record<Therapy, number>
        for (const th of THERAPIES) {
          medianCurrent[th] = arrMedian(districts.map((d) => d.scores[th].current))
          medianGrowth[th]  = arrMedian(districts.map((d) => d.scores[th].future - d.scores[th].current))
        }

        // ── Enrich each district with quadrant (once, shared across all views) ──
        for (const d of districts) {
          d.quadrant = {} as Record<Therapy, Quadrant>
          for (const th of THERAPIES) {
            const growth = d.scores[th].future - d.scores[th].current
            d.quadrant[th] = assignQuadrant(
              d.scores[th].current, growth,
              medianCurrent[th], medianGrowth[th],
            )
          }
        }

        // ── Join GeoJSON ──
        const scoresMap = new Map<string, DistrictScore>()
        for (const d of districts) scoresMap.set(d.districtId, d)

        let gapCount = 0
        for (const feat of geo.features) {
          const props = feat.properties as Record<string, string>
          let key = props.dt_code ? String(props.dt_code).trim() : null
          let score = key ? scoresMap.get(key) : undefined

          if (!score && props.district) {
            const geoName = String(props.district).toLowerCase().trim()
            const fallback = districts.find(d => d.districtName?.toLowerCase().trim() === geoName)
            if (fallback) {
              score = fallback
            }
          }

          if (!score) {
            gapCount++
            console.warn('[MAI] crosswalk gap:', props.district || '(no name)', props.st_nm || '')
          }
        }
        console.info(`[MAI] ${districts.length} districts | ${gapCount} GeoJSON features without score`)

        const medians       = computeMedians(districts, mock.weights)
        const ranksByTherapy = {} as AppData['ranksByTherapy']
        for (const th of THERAPIES) ranksByTherapy[th] = computeRanks(districts, th)

        const clusters: ClusterProfile[] = clustersRaw.profiles ?? []

        setState({
          loading: false,
          error: null,
          data: {
            geoJson: geo,
            scoresMap,
            districts,
            weights: mock.weights,
            medians,
            ranksByTherapy,
            n: districts.length,
            clusters,
            medianCurrent,
            medianGrowth,
          },
        })
      })
      .catch((err) => {
        setState({ data: null, loading: false, error: String(err) })
      })
  }, [])

  return state
}
