import { useRef, useMemo } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ReferenceArea, ResponsiveContainer,
  Label,
} from 'recharts'
import type { AppData, Therapy, Quadrant } from '../types/district'
import { captureAsPng, extractSvgFromContainer } from '../utils/export'

const QUADRANT_FILL: Record<Quadrant, string> = {
  Stars:          '#22C55E',
  'Cash Cows':    '#3B82F6',
  Emerging:       '#F97316',
  'Low Priority': '#9CA3AF',
}

const QUADRANT_LABEL_COLOR: Record<Quadrant, string> = {
  Stars:          '#15803D',
  'Cash Cows':    '#1D4ED8',
  Emerging:       '#C2410C',
  'Low Priority': '#6B7280',
}

interface ScatterPoint {
  x:        number   // current score
  y:        number   // growth delta
  z:        number   // demand pillar (bubble size)
  id:       string
  name:     string
  state:    string
  archetype?: string
  quadrant: Quadrant
}

interface CustomTooltipProps {
  active?:  boolean
  payload?: Array<{ payload: ScatterPoint }>
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg px-3 py-2 text-sm min-w-[180px]">
      <p className="font-bold text-gray-900 text-sm">{d.name}</p>
      <p className="text-gray-500 text-xs mb-1">{d.state}</p>
      <div className="grid grid-cols-2 gap-x-3 text-xs">
        <span className="text-gray-500">Current</span>
        <span className="font-semibold text-gray-800">{d.x.toFixed(1)}</span>
        <span className="text-gray-500">Growth Δ</span>
        <span className="font-semibold text-gray-800">{d.y >= 0 ? '+' : ''}{d.y.toFixed(1)}</span>
        <span className="text-gray-500">Demand</span>
        <span className="font-semibold text-gray-800">{d.z.toFixed(0)}</span>
      </div>
      {d.archetype && <p className="text-xs text-gray-400 mt-1 italic">{d.archetype}</p>}
      <p
        className="text-xs font-semibold mt-1"
        style={{ color: QUADRANT_LABEL_COLOR[d.quadrant] }}
      >
        {d.quadrant}
      </p>
    </div>
  )
}

interface OpportunityMatrixProps {
  data:               AppData
  therapy:            Therapy
  selectedDistrictId: string | null
  onDistrictSelect:   (id: string | null) => void
}

export function OpportunityMatrix({ data, therapy, selectedDistrictId, onDistrictSelect }: OpportunityMatrixProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const { districts, medianCurrent, medianGrowth } = data
  const medX = medianCurrent[therapy]
  const medY = medianGrowth[therapy]

  const chartData = useMemo<ScatterPoint[]>(() =>
    districts.map((d) => ({
      x:        d.scores[therapy].current,
      y:        d.scores[therapy].future - d.scores[therapy].current,
      z:        d.pillars[therapy].demand,
      id:       d.districtId,
      name:     d.districtName,
      state:    d.state,
      archetype: d.archetype,
      quadrant: d.quadrant?.[therapy] ?? 'Low Priority',
    })),
  [districts, therapy])

  const yValues = chartData.map((d) => d.y)
  const yMin = Math.floor(Math.min(...yValues) - 1)
  const yMax = Math.ceil(Math.max(...yValues) + 1)

  function handleDotClick(id: string) {
    onDistrictSelect(id === selectedDistrictId ? null : id)
  }

  const renderDot = (props: Record<string, unknown>) => {
    const { cx, cy, payload } = props as { cx: number; cy: number; payload: ScatterPoint }
    const r  = 4 + (payload.z / 100) * 9
    const color = QUADRANT_FILL[payload.quadrant]
    const isSelected = payload.id === selectedDistrictId
    return (
      <circle
        key={payload.id}
        cx={cx} cy={cy}
        r={isSelected ? r + 3 : r}
        fill={color}
        fillOpacity={isSelected ? 0.95 : 0.65}
        stroke={isSelected ? '#1D4ED8' : '#fff'}
        strokeWidth={isSelected ? 2.5 : 0.8}
        style={{ cursor: 'pointer' }}
        onClick={() => handleDotClick(payload.id)}
      />
    )
  }

  return (
    <div className="w-full h-full flex flex-col bg-white" ref={containerRef}>
      {/* Header */}
      <div className="px-6 pt-4 pb-2 border-b border-gray-100 flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-base font-bold text-gray-900">Opportunity Matrix</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Bubble size = Demand pillar score · Quadrant thresholds = national medians
            (Current ≥ {medX.toFixed(1)}, Growth Δ ≥ {medY.toFixed(1)})
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => containerRef.current && captureAsPng(containerRef.current, `MAI_matrix.png`)}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors"
          >
            Export PNG
          </button>
          <button
            onClick={() => containerRef.current && extractSvgFromContainer(containerRef.current, `MAI_matrix.svg`)}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors"
          >
            Export SVG
          </button>
        </div>
      </div>

      {/* Quadrant legend */}
      <div className="flex gap-4 px-6 py-2 shrink-0">
        {(Object.keys(QUADRANT_FILL) as Quadrant[]).map((q) => (
          <div key={q} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: QUADRANT_FILL[q] }} />
            <span className="text-xs text-gray-600">{q}</span>
          </div>
        ))}
        <span className="text-xs text-gray-400 ml-2">Click a district to open detail panel</span>
      </div>

      {/* Chart */}
      <div className="flex-1 px-4 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 40, bottom: 40, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />

            {/* Quadrant background shading */}
            <ReferenceArea x1={medX} x2={100}  y1={medY} y2={yMax} fill="#22C55E" fillOpacity={0.04} />
            <ReferenceArea x1={0}    x2={medX}  y1={medY} y2={yMax} fill="#F97316" fillOpacity={0.04} />
            <ReferenceArea x1={medX} x2={100}  y1={yMin} y2={medY} fill="#3B82F6" fillOpacity={0.04} />
            <ReferenceArea x1={0}    x2={medX}  y1={yMin} y2={medY} fill="#9CA3AF" fillOpacity={0.04} />

            {/* Quadrant labels */}
            <ReferenceArea x1={medX} x2={100}  y1={medY} y2={yMax} fill="none"
              label={{ value: 'Stars', fill: '#15803D', fontSize: 11, fontWeight: 700, position: 'insideTopRight' }} />
            <ReferenceArea x1={0}    x2={medX}  y1={medY} y2={yMax} fill="none"
              label={{ value: 'Emerging', fill: '#C2410C', fontSize: 11, fontWeight: 700, position: 'insideTopLeft' }} />
            <ReferenceArea x1={medX} x2={100}  y1={yMin} y2={medY} fill="none"
              label={{ value: 'Cash Cows', fill: '#1D4ED8', fontSize: 11, fontWeight: 700, position: 'insideBottomRight' }} />
            <ReferenceArea x1={0}    x2={medX}  y1={yMin} y2={medY} fill="none"
              label={{ value: 'Low Priority', fill: '#6B7280', fontSize: 11, fontWeight: 700, position: 'insideBottomLeft' }} />

            {/* Threshold lines */}
            <ReferenceLine x={medX} stroke="#374151" strokeDasharray="5 3" strokeWidth={1.5} />
            <ReferenceLine y={medY} stroke="#374151" strokeDasharray="5 3" strokeWidth={1.5} />
            <ReferenceLine y={0} stroke="#D1D5DB" strokeWidth={1} />

            <XAxis type="number" dataKey="x" domain={[0, 100]} tick={{ fontSize: 11, fill: '#6B7280' }}>
              <Label value="Current Attractiveness Score" offset={-10} position="insideBottom" style={{ fontSize: 12, fill: '#374151', fontWeight: 600 }} />
            </XAxis>
            <YAxis type="number" dataKey="y" domain={[yMin, yMax]} tick={{ fontSize: 11, fill: '#6B7280' }}>
              <Label value="Growth Δ (2030 − current)" angle={-90} position="insideLeft" offset={10} style={{ fontSize: 12, fill: '#374151', fontWeight: 600 }} />
            </YAxis>

            <Tooltip content={<CustomTooltip />} />

            <Scatter data={chartData} shape={renderDot as never} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
