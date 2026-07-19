import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, LabelList, ResponsiveContainer,
} from 'recharts'
import type { PillarScores, Therapy } from '../types/district'

const PILLAR_COLORS: Record<string, string> = {
  demand: '#F97316',
  monetization: '#8B5CF6',
  access: '#06B6D4',
  growth: '#22C55E',
}

const PILLAR_LABELS: Record<string, string> = {
  demand: 'Demand',
  monetization: 'Monetization',
  access: 'Access',
  growth: 'Growth',
}

interface PillarWaterfallProps {
  pillars: PillarScores
  total: number
  therapy: Therapy
}

export function PillarWaterfall({ pillars, total }: PillarWaterfallProps) {
  const data = Object.entries(pillars)
    .map(([key, value]) => ({ name: PILLAR_LABELS[key] ?? key, key, value: +value.toFixed(2) }))
    .sort((a, b) => b.value - a.value)

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Pillar Scores</p>
        <p className="text-xs text-gray-500">Headline: <span className="font-bold text-gray-800">{total.toFixed(1)}</span></p>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart layout="vertical" data={data} margin={{ top: 2, right: 40, bottom: 2, left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F3F4F6" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11, fill: '#374151' }}
            axisLine={false}
            tickLine={false}
            width={75}
          />
          <Tooltip
            formatter={(v: number) => [`${v.toFixed(1)} / 100`, 'Score']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #E5E7EB' }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={20}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={PILLAR_COLORS[entry.key] ?? '#6B7280'} />
            ))}
            <LabelList
              dataKey="value"
              position="right"
              formatter={(v: number) => v.toFixed(1)}
              style={{ fontSize: 10, fill: '#6B7280' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
