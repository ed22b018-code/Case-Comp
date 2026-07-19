export type Therapy = 'overall' | 'chronic' | 'acute'
export type ViewMode = 'current' | 'future' | 'growth'
export type Pillar = 'demand' | 'monetization' | 'access' | 'growth'
export type Quadrant = 'Stars' | 'Cash Cows' | 'Emerging' | 'Low Priority'
export type Pane = 'map' | 'matrix' | 'simulator' | 'rankings'
export type ColorMode = 'score' | 'archetype'

export const THERAPIES: Therapy[] = ['overall', 'chronic', 'acute']
export const PILLARS: Pillar[] = ['demand', 'monetization', 'access', 'growth']
export const PANES: { value: Pane; label: string }[] = [
  { value: 'map',       label: 'Map' },
  { value: 'matrix',    label: 'Matrix' },
  { value: 'simulator', label: 'Simulator' },
  { value: 'rankings',  label: 'Rankings' },
]

export interface TherapyScore {
  current: number
  future: number
}

export interface PillarScores {
  demand: number
  monetization: number
  access: number
  growth: number
}

export interface DistrictScore {
  districtId:   string
  districtName: string
  state:        string
  joinMethod?:  'dt_code' | 'fallback'
  clusterLabel?: number
  archetype?:   string
  quadrant?:    Record<Therapy, Quadrant>
  scores:  Record<Therapy, TherapyScore>
  pillars: Record<Therapy, PillarScores>
}

export interface RankedDistrict extends DistrictScore {
  ranks: Record<Therapy, number>
}

export interface ClusterProfile {
  clusterId:    number
  archetype:    string
  n_districts:  number
  demand:       number
  monetization: number
  access:       number
  growth:       number
}

export interface MockData {
  weights:   Record<Therapy, PillarScores>
  districts: DistrictScore[]
}

export interface AppData {
  geoJson:         GeoJSON.FeatureCollection
  scoresMap:       Map<string, DistrictScore>
  districts:       DistrictScore[]
  weights:         Record<Therapy, PillarScores>
  medians:         Record<Therapy, PillarScores>
  ranksByTherapy:  Record<Therapy, Map<string, number>>
  n:               number
  clusters:        ClusterProfile[]
  medianCurrent:   Record<Therapy, number>
  medianGrowth:    Record<Therapy, number>
}
