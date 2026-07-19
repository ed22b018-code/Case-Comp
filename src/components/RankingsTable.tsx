import { useState, useMemo, useEffect } from 'react'
import type { AppData, Therapy, ViewMode, Quadrant, DistrictScore } from '../types/district'
import { getDisplayValue } from '../utils/scoring'
import { downloadCsv } from '../utils/export'

type SortCol = 'rank' | 'district' | 'state' | 'archetype' | 'current' | 'future' | 'delta' | 'quadrant'

const COL_HEADERS: { key: SortCol; label: string }[] = [
  { key: 'rank',      label: '#'        },
  { key: 'district',  label: 'District' },
  { key: 'state',     label: 'State'    },
  { key: 'archetype', label: 'Archetype'},
  { key: 'current',   label: 'Current'  },
  { key: 'future',    label: '2030'     },
  { key: 'delta',     label: 'Δ'        },
  { key: 'quadrant',  label: 'Quadrant' },
]

const QUADRANT_BADGE: Record<Quadrant, string> = {
  Stars:          'bg-green-100 text-green-800',
  'Cash Cows':    'bg-blue-100 text-blue-800',
  Emerging:       'bg-orange-100 text-orange-800',
  'Low Priority': 'bg-gray-100 text-gray-600',
}

interface RankingsTableProps {
  data:               AppData
  therapy:            Therapy
  view:               ViewMode
  selectedDistrictId: string | null
  onDistrictSelect:   (id: string | null) => void
}

function scoreDistrict(d: DistrictScore, therapy: Therapy): { current: number; future: number; delta: number } {
  const current = d.scores[therapy].current
  const future  = d.scores[therapy].future
  return { current, future, delta: future - current }
}

export function RankingsTable({ data, therapy, view, selectedDistrictId, onDistrictSelect }: RankingsTableProps) {
  const { districts } = data

  const [sortCol,     setSortCol]     = useState<SortCol>('current')
  const [sortDir,     setSortDir]     = useState<'asc' | 'desc'>('desc')
  const [stateFilter, setStateFilter] = useState('all')
  const [search,      setSearch]      = useState('')

  useEffect(() => {
    if (view === 'current') setSortCol('current')
    else if (view === 'future') setSortCol('future')
    else if (view === 'growth') setSortCol('delta')
    setSortDir('desc')
  }, [view])

  const allStates = useMemo(
    () => [...new Set(districts.map((d) => d.state))].sort(),
    [districts],
  )

  function handleSort(col: SortCol) {
    if (sortCol === col) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setSortCol(col); setSortDir('desc') }
  }

  const sorted = useMemo(() => {
    let rows = districts
    if (stateFilter !== 'all') rows = rows.filter((d) => d.state === stateFilter)
    if (search) {
      const q = search.toLowerCase()
      rows = rows.filter((d) =>
        d.districtName.toLowerCase().includes(q) || d.state.toLowerCase().includes(q),
      )
    }

    return [...rows].sort((a, b) => {
      const { current: ac, future: af, delta: ad } = scoreDistrict(a, therapy)
      const { current: bc, future: bf, delta: bd } = scoreDistrict(b, therapy)
      let diff = 0
      switch (sortCol) {
        case 'district':  diff = a.districtName.localeCompare(b.districtName); break
        case 'state':     diff = a.state.localeCompare(b.state); break
        case 'archetype': diff = (a.archetype ?? '').localeCompare(b.archetype ?? ''); break
        case 'quadrant':  diff = (a.quadrant?.[therapy] ?? '').localeCompare(b.quadrant?.[therapy] ?? ''); break
        case 'current':   diff = ac - bc; break
        case 'future':    diff = af - bf; break
        case 'delta':     diff = ad - bd; break
        default:          diff = ac - bc
      }
      return sortDir === 'desc' ? -diff : diff
    })
  }, [districts, therapy, stateFilter, search, sortCol, sortDir])

  function handleExport() {
    const rows = sorted.map((d, i) => {
      const { current, future, delta } = scoreDistrict(d, therapy)
      return {
        Rank:         i + 1,
        District:     d.districtName,
        State:        d.state,
        Archetype:    d.archetype ?? '',
        Current:      current.toFixed(1),
        Future_2030:  future.toFixed(1),
        Growth_Delta: delta.toFixed(1),
        Quadrant:     d.quadrant?.[therapy] ?? '',
      }
    })
    downloadCsv(rows, `MAI_rankings_${therapy}_${view}.csv`)
  }

  const sortIndicator = (col: SortCol) =>
    sortCol === col ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''

  return (
    <div className="w-full h-full flex flex-col bg-white overflow-hidden">
      {/* Toolbar */}
      <div className="px-6 pt-4 pb-3 border-b border-gray-100 shrink-0 flex flex-wrap gap-3 items-center">
        <h2 className="text-base font-bold text-gray-900 shrink-0">District Rankings</h2>

        {/* Search */}
        <input
          type="text"
          placeholder="Search district or state…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 w-52 focus:outline-none focus:ring-1 focus:ring-orange-400"
        />

        {/* State filter */}
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-orange-400"
        >
          <option value="all">All states</option>
          {allStates.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <span className="text-xs text-gray-400 flex-1">
          {sorted.length} of {districts.length} districts · click column header to sort · click row to open detail
        </span>

        <button
          onClick={handleExport}
          className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors shrink-0"
        >
          Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 bg-gray-900 text-white z-10">
            <tr>
              {COL_HEADERS.map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => handleSort(key)}
                  className="px-3 py-2.5 text-left text-xs font-semibold tracking-wide cursor-pointer select-none hover:bg-gray-700 transition-colors"
                >
                  {label}{sortIndicator(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((d, i) => {
              const { current, future, delta } = scoreDistrict(d, therapy)
              const quad     = d.quadrant?.[therapy]
              const isActive = d.districtId === selectedDistrictId
              const primary  = getDisplayValue(d, therapy, view)

              return (
                <tr
                  key={d.districtId}
                  onClick={() => onDistrictSelect(isActive ? null : d.districtId)}
                  className={`border-b border-gray-100 cursor-pointer transition-colors ${
                    isActive ? 'bg-blue-50' : i % 2 === 0 ? 'bg-white hover:bg-orange-50' : 'bg-gray-50/60 hover:bg-orange-50'
                  }`}
                >
                  <td className="px-3 py-2 text-xs font-bold text-gray-400 w-10">{i + 1}</td>
                  <td className="px-3 py-2 font-semibold text-gray-900 text-xs">
                    {d.districtName}
                    {view !== 'current' && (
                      <span className="ml-1.5 font-normal text-orange-600">{primary.toFixed(1)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500">{d.state}</td>
                  <td className="px-3 py-2 text-xs text-gray-500 max-w-[160px] truncate">{d.archetype ?? '—'}</td>
                  <td className="px-3 py-2 text-xs font-semibold text-gray-800">{current.toFixed(1)}</td>
                  <td className="px-3 py-2 text-xs font-semibold text-gray-800">{future.toFixed(1)}</td>
                  <td className={`px-3 py-2 text-xs font-semibold ${delta >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    {delta >= 0 ? '+' : ''}{delta.toFixed(1)}
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
