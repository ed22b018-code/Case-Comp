import type { AppData, DistrictScore, Therapy, ViewMode } from '../types/district'
import { THERAPIES } from '../types/district'
import { getDisplayValue } from '../utils/scoring'
import { PillarWaterfall } from './PillarWaterfall'
import { PillarRadar } from './PillarRadar'

const THERAPY_LABEL: Record<Therapy, string> = {
  overall: 'Overall',
  chronic: 'Chronic',
  acute: 'Acute',
}

const VIEW_LABEL: Record<ViewMode, string> = {
  current: 'Current',
  future: '2030',
  growth: 'Growth Δ',
}

const THERAPY_ACCENTS: Record<Therapy, string> = {
  overall: 'bg-orange-50 text-orange-700 ring-orange-200',
  chronic: 'bg-violet-50 text-violet-700 ring-violet-200',
  acute: 'bg-cyan-50 text-cyan-700 ring-cyan-200',
}

interface TherapyScoreTileProps {
  label: string
  district: DistrictScore
  therapy: Therapy
  active: boolean
  rank: number
  n: number
}

function TherapyScoreTile({ label, district, therapy, active, rank, n }: TherapyScoreTileProps) {
  const s = district.scores[therapy]
  const growth = s.future - s.current
  return (
    <div
      className={`rounded-xl p-3 ring-1 transition-all ${
        active ? THERAPY_ACCENTS[therapy] : 'bg-gray-50 text-gray-600 ring-gray-200'
      }`}
    >
      <p className={`text-xs font-semibold mb-1 ${active ? '' : 'text-gray-500'}`}>{label}</p>
      <p className="text-2xl font-black leading-none">{s.current.toFixed(1)}</p>
      <p className="text-[10px] mt-0.5 opacity-70">
        2030: {s.future.toFixed(1)} &nbsp;·&nbsp; Δ {growth >= 0 ? '+' : ''}{growth.toFixed(1)}
      </p>
      <p className="text-[10px] mt-1 opacity-60">Rank {rank} / {n}</p>
    </div>
  )
}

interface DistrictPanelProps {
  district: DistrictScore | null
  therapy: Therapy
  view: ViewMode
  data: AppData
  onClose: () => void
}

export function DistrictPanel({ district, therapy, view, data, onClose }: DistrictPanelProps) {
  if (!district) return null

  const { weights, medians, ranksByTherapy, n } = data

  const displayValue = getDisplayValue(district, therapy, view)
  const pillars = district.pillars[therapy]
  const total = district.scores[therapy].current

  return (
    <aside className="w-96 shrink-0 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-gray-100 flex items-start justify-between">
        <div>
          <h2 className="text-base font-bold text-gray-900 leading-tight">{district.districtName}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{district.state}</p>
          <p className="text-xs text-gray-400 mt-1">
            {VIEW_LABEL[view]} · {THERAPY_LABEL[therapy]} score:{' '}
            <span className="font-bold text-gray-700">
              {view === 'growth' && displayValue >= 0 ? '+' : ''}{displayValue.toFixed(1)}
            </span>
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 transition-colors p-1 -mr-1 mt-0.5"
          aria-label="Close panel"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Three therapy score tiles */}
        <section>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Therapy Scores</p>
          <div className="grid grid-cols-3 gap-2">
            {THERAPIES.map((th) => (
              <TherapyScoreTile
                key={th}
                label={THERAPY_LABEL[th]}
                district={district}
                therapy={th}
                active={th === therapy}
                rank={ranksByTherapy[th].get(district.districtId) ?? 0}
                n={n}
              />
            ))}
          </div>
        </section>

        {/* Pillar waterfall */}
        <section className="border-t border-gray-100 pt-4">
          <PillarWaterfall pillars={pillars} total={total} therapy={therapy} />
        </section>

        {/* Radar chart */}
        <section className="border-t border-gray-100 pt-4">
          <PillarRadar
            district={district}
            therapy={therapy}
            medians={medians}
            weights={weights}
          />
        </section>
      </div>

      {/* Footer badge */}
      {district.joinMethod === 'fallback' && (
        <div className="px-5 py-2 border-t border-gray-100 bg-amber-50">
          <p className="text-[10px] text-amber-600">Joined via fallback key (missing dt_code in GeoJSON)</p>
        </div>
      )}
    </aside>
  )
}
