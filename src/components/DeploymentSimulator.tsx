import { useState, useMemo } from 'react'
import type { AppData, Therapy, Quadrant, DistrictScore } from '../types/district'
import { downloadCsv } from '../utils/export'

type Strategy = 'current' | 'future' | 'balanced' | 'emerging'

const STRATEGY_OPTS: { value: Strategy; label: string; description: string }[] = [
  { value: 'current',  label: 'Maximize Current', description: 'Highest present attractiveness'       },
  { value: 'future',   label: 'Maximize Future',  description: 'Highest 2030 projected score'         },
  { value: 'balanced', label: 'Balanced',          description: 'Weighted blend of current + future'   },
  { value: 'emerging', label: 'Emerging Bets',     description: 'Fast-rising districts below median — latent-demand markets' },
]

const QUADRANT_BADGE: Record<Quadrant, string> = {
  Stars:          'bg-green-100 text-green-800',
  'Cash Cows':    'bg-blue-100 text-blue-800',
  Emerging:       'bg-orange-100 text-orange-800',
  'Low Priority': 'bg-gray-100 text-gray-600',
}

interface SimulatorRow extends DistrictScore {
  simScore: number
  rank:     number
  growth:   number
}

interface DeploymentSimulatorProps {
  data:               AppData
  therapy:            Therapy
  selectedDistrictId: string | null
  onDistrictSelect:   (id: string | null) => void
}

export function DeploymentSimulator({ data, therapy, selectedDistrictId, onDistrictSelect }: DeploymentSimulatorProps) {
  const { districts, medianCurrent } = data

  const [n,         setN]        = useState(50)
  const [strategy,  setStrategy] = useState<Strategy>('current')
  const [weight,    setWeight]   = useState(0.5)   // growth weight for Balanced
  const [stateFilter, setStateFilter] = useState('all')
  const [excludeRaw,  setExcludeRaw]  = useState('')

  const allStates = useMemo(
    () => [...new Set(districts.map((d) => d.state))].sort(),
    [districts],
  )

  const excludeSet = useMemo(() => {
    const entries = excludeRaw.split(/[\n,;]+/).map((s) => s.trim().toLowerCase()).filter(Boolean)
    return new Set(entries)
  }, [excludeRaw])

  const results = useMemo<SimulatorRow[]>(() => {
    const medCurrent = medianCurrent[therapy]

    // 1. Filter
    let pool = districts.filter((d) => {
      if (stateFilter !== 'all' && d.state !== stateFilter) return false
      const nameMatch = excludeSet.has(d.districtName.toLowerCase())
      const idMatch   = excludeSet.has(d.districtId.toLowerCase())
      return !nameMatch && !idMatch
    })

    // 2. Emerging Bets: restrict to below-median-current districts only
    if (strategy === 'emerging') {
      pool = pool.filter((d) => d.scores[therapy].current < medCurrent)
    }

    // 3. Score + sort
    const scored = pool.map((d) => {
      const current = d.scores[therapy].current
      const future  = d.scores[therapy].future
      const growth  = future - current
      let simScore: number
      if (strategy === 'current')  simScore = current
      else if (strategy === 'future')   simScore = future
      else if (strategy === 'balanced') simScore = (1 - weight) * current + weight * future
      else /* emerging */               simScore = growth
      return { ...d, simScore, growth } as SimulatorRow
    })

    scored.sort((a, b) => b.simScore - a.simScore)

    // 4. Top-N with ranks
    return scored.slice(0, n).map((row, i) => ({ ...row, rank: i + 1 }))
  }, [districts, therapy, strategy, weight, stateFilter, excludeSet, n, medianCurrent])

  function handleExport() {
    const rows = results.map((r) => ({
      Rank:         r.rank,
      District:     r.districtName,
      State:        r.state,
      Archetype:    r.archetype ?? '',
      Current:      r.scores[therapy].current.toFixed(1),
      Future_2030:  r.scores[therapy].future.toFixed(1),
      Growth_Delta: r.growth.toFixed(1),
      Quadrant:     r.quadrant?.[therapy] ?? '',
      Score_Used:   r.simScore.toFixed(2),
    }))
    downloadCsv(rows, `MAI_simulator_${therapy}_${strategy}_top${n}.csv`)
  }

  return (
    <div className="w-full h-full flex flex-col bg-white overflow-hidden">
      {/* Controls header */}
      <div className="px-6 pt-4 pb-3 border-b border-gray-100 shrink-0 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900">Deployment Simulator</h2>
          <button
            onClick={handleExport}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors"
          >
            Export CSV
          </button>
        </div>

        {/* N slider */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-gray-600 w-36 shrink-0">
            Districts to enter: <span className="text-orange-600 font-bold">{n}</span>
          </span>
          <input
            type="range" min={1} max={Math.min(250, districts.length)}
            value={n}
            onChange={(e) => setN(+e.target.value)}
            className="flex-1 accent-orange-500"
          />
        </div>

        {/* Strategy selector */}
        <div className="flex flex-wrap gap-2">
          {STRATEGY_OPTS.map((s) => (
            <button
              key={s.value}
              title={s.description}
              onClick={() => setStrategy(s.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                strategy === s.value
                  ? 'bg-orange-500 text-white border-orange-500 shadow-sm'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Balanced weight slider (only visible when Balanced selected) */}
        {strategy === 'balanced' && (
          <div className="flex items-center gap-3 bg-orange-50 rounded-lg px-3 py-2">
            <span className="text-xs text-orange-800 w-48 shrink-0">
              Weight future growth: <span className="font-bold">{weight.toFixed(2)}</span>
              <span className="text-orange-600 ml-1">({weight === 0 ? 'Pure current / harvest' : weight === 1 ? 'Pure growth / invest' : 'Blended'})</span>
            </span>
            <input
              type="range" min={0} max={1} step={0.05}
              value={weight}
              onChange={(e) => setWeight(+e.target.value)}
              className="flex-1 accent-orange-500"
            />
            <span className="text-[10px] text-orange-700 w-48 text-right shrink-0">
              Score = {(1-weight).toFixed(2)}×current + {weight.toFixed(2)}×future
            </span>
          </div>
        )}

        {strategy === 'emerging' && (
          <p className="text-xs text-orange-700 bg-orange-50 rounded-lg px-3 py-1.5">
            Emerging Bets: ranking by growth Δ among districts <em>below</em> the national current-score median — surfaces latent-demand markets current practice misses.
          </p>
        )}

        {/* Filters */}
        <div className="flex gap-3 items-start">
          <div className="flex items-center gap-2 shrink-0">
            <label className="text-xs font-medium text-gray-600">State</label>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-orange-400"
            >
              <option value="all">All states</option>
              {allStates.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-600 block mb-1">
              Exclude districts <span className="text-gray-400 font-normal">(names or IDs, comma- or line-separated)</span>
            </label>
            <textarea
              value={excludeRaw}
              onChange={(e) => setExcludeRaw(e.target.value)}
              placeholder="e.g. Mumbai, 123456"
              rows={2}
              className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-orange-400"
            />
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="px-6 py-2 bg-gray-50 border-b border-gray-100 shrink-0">
        <p className="text-xs text-gray-500">
          Showing top <span className="font-semibold text-gray-700">{results.length}</span> of{' '}
          {strategy === 'emerging'
            ? `${districts.filter(d => d.scores[therapy].current < medianCurrent[therapy]).length} below-median districts`
            : `${districts.length} districts`}
          {stateFilter !== 'all' && ` in ${stateFilter}`}
          {excludeSet.size > 0 && ` (${excludeSet.size} excluded)`}
        </p>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 bg-gray-900 text-white z-10">
            <tr>
              {['#', 'District', 'State', 'Archetype', 'Current', '2030', 'Δ', 'Quadrant'].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, i) => {
              const quad     = row.quadrant?.[therapy]
              const isActive = row.districtId === selectedDistrictId
              return (
                <tr
                  key={row.districtId}
                  onClick={() => onDistrictSelect(isActive ? null : row.districtId)}
                  className={`border-b border-gray-100 cursor-pointer transition-colors ${
                    isActive ? 'bg-blue-50' : i % 2 === 0 ? 'bg-white hover:bg-orange-50' : 'bg-gray-50 hover:bg-orange-50'
                  }`}
                >
                  <td className="px-3 py-2 text-xs font-bold text-gray-400">{row.rank}</td>
                  <td className="px-3 py-2 font-semibold text-gray-900 text-xs">{row.districtName}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{row.state}</td>
                  <td className="px-3 py-2 text-xs text-gray-500 max-w-[140px] truncate">{row.archetype ?? '—'}</td>
                  <td className="px-3 py-2 text-xs font-semibold text-gray-800">
                    {row.scores[therapy].current.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-xs font-semibold text-gray-800">
                    {row.scores[therapy].future.toFixed(1)}
                  </td>
                  <td className={`px-3 py-2 text-xs font-semibold ${row.growth >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    {row.growth >= 0 ? '+' : ''}{row.growth.toFixed(1)}
                  </td>
                  <td className="px-3 py-2">
                    {quad && (
                      <span className={`inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${QUADRANT_BADGE[quad]}`}>
                        {quad}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
