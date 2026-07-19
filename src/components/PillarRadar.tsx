import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Legend, ResponsiveContainer, Tooltip,
} from 'recharts'
import type { DistrictScore, Therapy, PillarScores } from '../types/district'
import { PILLARS } from '../types/district'
import { getPillarRawScores } from '../utils/scoring'

const PILLAR_DISPLAY: Record<string, string> = {
  demand: 'Demand',
  monetization: 'Monetization',
  access: 'Access',
  growth: 'Growth',
}

interface PillarRadarProps {
  district: DistrictScore
  therapy: Therapy
  medians: Record<Therapy, PillarScores>
  weights: Record<Therapy, PillarScores>
}

export function PillarRadar({ district, therapy, medians, weights }: PillarRadarProps) {
  const rawScores = getPillarRawScores(district, therapy, weights)
  const medianScores = medians[therapy]

  const data = PILLARS.map((p) => ({
    pillar: PILLAR_DISPLAY[p],
    District: +rawScores[p].toFixed(1),
    Median: +medianScores[p].toFixed(1),
  }))

  return (
    <div>
      <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
        Pillar Scores vs National Median
      </p>
      <ResponsiveContainer width="100%" height={230}>
        <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="#E5E7EB" />
          <PolarAngleAxis
            dataKey="pillar"
            tick={{ fontSize: 11, fill: '#374151' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: '#9CA3AF' }}
            tickCount={4}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #E5E7EB' }}
            formatter={(v: number, name: string) => [`${v.toFixed(1)}`, name]}
          />
          <Radar
            name="District"
            dataKey="District"
            stroke="#E57200"
            fill="#E57200"
            fillOpacity={0.25}
            strokeWidth={2}
          />
          <Radar
            name="Median"
            dataKey="Median"
            stroke="#6B7280"
            fill="#6B7280"
            fillOpacity={0.1}
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
            iconType="circle"
            iconSize={8}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
