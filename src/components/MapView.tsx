import { useEffect, useRef } from 'react'
import { MapContainer, GeoJSON } from 'react-leaflet'
import type { GeoJSON as LeafletGeoJSON, PathOptions, Layer } from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { AppData, Therapy, ViewMode, ColorMode } from '../types/district'
import { getDisplayValue, getDomain } from '../utils/scoring'
import { valueToColor, legendStops, NO_DATA_COLOR, clusterColor, CLUSTER_COLORS } from '../utils/colorScale'
import { captureAsPng, extractSvgFromContainer } from '../utils/export'

const INDIA_CENTER: [number, number] = [22.5, 82.5]
const INDIA_ZOOM = 5

const THERAPY_LABEL: Record<Therapy, string> = {
  overall: 'Overall MAI',
  chronic: 'Chronic MAI',
  acute:   'Acute MAI',
}

const VIEW_LABEL: Record<ViewMode, string> = {
  current: 'Current Score',
  future:  '2030 Projected',
  growth:  'Growth Δ',
}

interface MapViewProps {
  data:               AppData
  therapy:            Therapy
  view:               ViewMode
  colorMode:          ColorMode
  selectedDistrictId: string | null
  onDistrictSelect:   (id: string | null) => void
}

export function MapView({ data, therapy, view, colorMode, selectedDistrictId, onDistrictSelect }: MapViewProps) {
  const { geoJson, scoresMap, districts, clusters } = data
  const geoJsonRef = useRef<LeafletGeoJSON | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedIdRef = useRef(selectedDistrictId)
  useEffect(() => {
    selectedIdRef.current = selectedDistrictId
  }, [selectedDistrictId])

  const domain = getDomain(districts, therapy, view)

  function matchFeature(feature: GeoJSON.Feature | undefined) {
    if (!feature) return { key: null, score: undefined, name: '(unknown)', state: '', isStatePolygon: false }
    const props = feature.properties as Record<string, any>
    
    const isStatePolygon = !props.dt_code && !props.district

    let key = props.dt_code ? String(props.dt_code).trim() : null
    let score = key ? scoresMap.get(key) : undefined
    
    if (!score && props.district) {
      const geoName = String(props.district).toLowerCase().trim()
      const fallback = districts.find(d => d.districtName?.toLowerCase().trim() === geoName)
      if (fallback) {
        score = fallback
        key = fallback.districtId
      }
    }

    const name = score?.districtName || props.district || '(unknown)'
    const state = props.st_nm || ''

    return { key, score, name, state, isStatePolygon }
  }

  function featureStyle(feature: GeoJSON.Feature | undefined): PathOptions {
    if (!feature) return { fillColor: NO_DATA_COLOR, fillOpacity: 0.7, weight: 0.5, color: '#fff' }
    
    const { key, score, isStatePolygon } = matchFeature(feature)

    // Option B: Style state polygons as transparent outlines with no interactivity
    if (isStatePolygon) {
      return {
        fill: false,
        weight: 1.5,
        color: '#94a3b8', // subtle outline for states
        interactive: false // prevents intercepting hovers/clicks
      }
    }

    const isSelected = key && key === selectedDistrictId

    const strokeOpts: PathOptions = {
      weight: isSelected ? 2.5 : 0.7,
      color:  isSelected ? '#1D4ED8' : '#fff',
    }

    if (!score) {
      return { fillColor: NO_DATA_COLOR, fillOpacity: 0.6, ...strokeOpts }
    }

    if (colorMode === 'archetype') {
      return {
        fillColor:   clusterColor(score.clusterLabel),
        fillOpacity: 0.85,
        ...strokeOpts,
      }
    }

    const value = getDisplayValue(score, therapy, view)
    return {
      fillColor:   valueToColor(value, domain, view),
      fillOpacity: 0.85,
      ...strokeOpts,
    }
  }

  function onEachFeature(feature: GeoJSON.Feature, layer: Layer) {
    const { key, score, name, state, isStatePolygon } = matchFeature(feature)

    if (isStatePolygon) return // skip tooltip and events for state boundaries

    const tooltipContent = score
      ? `<strong>${name}</strong><br/>${state}<br/>${
          colorMode === 'archetype'
            ? `<em>${score.archetype ?? 'Unknown cluster'}</em>`
            : `${THERAPY_LABEL[therapy]}: <strong>${getDisplayValue(score, therapy, view).toFixed(1)}</strong>`
        }`
      : `<strong>${name}</strong><br/>${state}<br/><em>No data</em>`

    ;(layer as import('leaflet').Path).bindTooltip(tooltipContent, {
      sticky: true, opacity: 0.95, className: 'mai-tooltip',
    })

    layer.on({
      mouseover(e) {
        const l = e.target as import('leaflet').Path
        if (key !== selectedIdRef.current) l.setStyle({ weight: 2, color: '#374151' })
        l.bringToFront()
      },
      mouseout(e) {
        const l = e.target as import('leaflet').Path
        l.setStyle(featureStyle(feature))
        if (key === selectedIdRef.current) {
          l.setStyle({ weight: 2.5, color: '#1D4ED8' })
        }
      },
      click() {
        if (score && key) {
          onDistrictSelect(key === selectedIdRef.current ? null : key)
        }
      },
    })
  }

  useEffect(() => {
    if (!geoJsonRef.current) return
    geoJsonRef.current.setStyle((feature) => featureStyle(feature))
    geoJsonRef.current.eachLayer((layer) => {
      const feat = (layer as { feature?: GeoJSON.Feature }).feature
      if (!feat) return
      const { key, isStatePolygon } = matchFeature(feat)
      if (isStatePolygon) return
      if (key && key === selectedDistrictId) {
        ;(layer as import('leaflet').Path).setStyle({ weight: 2.5, color: '#1D4ED8' })
      }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [therapy, view, colorMode, selectedDistrictId, domain[0], domain[1]])

  const stops = legendStops(view, domain)

  return (
    <div className="relative w-full h-full bg-gray-50" ref={containerRef}>
      <MapContainer
        center={INDIA_CENTER}
        zoom={INDIA_ZOOM}
        className="w-full h-full"
        zoomControl={true}
        attributionControl={false}
      >
        {/* No TileLayer — pure SVG GeoJSON for offline use and clean export */}
        <GeoJSON
          key={`${therapy}-${view}-${colorMode}-${domain[0]}-${domain[1]}`}
          ref={geoJsonRef}
          data={geoJson}
          style={featureStyle}
          onEachFeature={onEachFeature}
        />
      </MapContainer>

      {/* Score legend */}
      {colorMode === 'score' && (
        <div className="absolute bottom-6 left-4 bg-white/90 backdrop-blur-sm rounded-xl shadow-lg px-4 py-3 z-[1000] min-w-[180px]">
          <p className="text-xs font-semibold text-gray-700 mb-2">
            {THERAPY_LABEL[therapy]} · {VIEW_LABEL[view]}
          </p>
          <div className="flex gap-0.5 mb-1">
            {stops.map((s, i) => (
              <div key={i} className="flex-1 h-3 rounded-sm" style={{ backgroundColor: s.color }} />
            ))}
          </div>
          <div className="flex justify-between">
            <span className="text-[10px] text-gray-500">{stops[0].label}</span>
            <span className="text-[10px] text-gray-500">{stops[stops.length - 1].label}</span>
          </div>
          <div className="mt-1.5 flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-gray-200" />
            <span className="text-[10px] text-gray-500">No data</span>
          </div>
        </div>
      )}

      {/* Archetype legend */}
      {colorMode === 'archetype' && clusters.length > 0 && (
        <div className="absolute bottom-6 left-4 bg-white/90 backdrop-blur-sm rounded-xl shadow-lg px-4 py-3 z-[1000] min-w-[220px] max-h-[60vh] overflow-y-auto">
          <p className="text-xs font-semibold text-gray-700 mb-2">Market Archetypes</p>
          {clusters.map((c) => (
            <div key={c.clusterId} className="flex items-center gap-2 py-0.5">
              <div
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: CLUSTER_COLORS[c.clusterId % CLUSTER_COLORS.length] }}
              />
              <span className="text-[10px] text-gray-700 leading-tight">
                {c.archetype} <span className="text-gray-400">({c.n_districts})</span>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* District count badge */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur-sm rounded-full shadow px-3 py-1 z-[1000]">
        <span className="text-xs text-gray-600 font-medium">{data.n} districts scored</span>
      </div>

      {/* Export buttons */}
      <div className="absolute top-3 right-4 flex gap-2 z-[1000]">
        <button
          title="Export full map view at 2x resolution (recommended for slides)"
          onClick={() => containerRef.current && captureAsPng(containerRef.current, `MAI_map_${therapy}_${view}.png`)}
          className="bg-white/90 hover:bg-white backdrop-blur-sm text-gray-700 text-[11px] font-medium px-3 py-1.5 rounded-lg shadow border border-gray-200 transition-colors"
        >
          Export PNG
        </button>
        <button
          title="Export map paths as vector SVG (legend not included — use PNG for slides)"
          onClick={() => containerRef.current && extractSvgFromContainer(containerRef.current, `MAI_map_${therapy}_${view}.svg`)}
          className="bg-white/90 hover:bg-white backdrop-blur-sm text-gray-700 text-[11px] font-medium px-3 py-1.5 rounded-lg shadow border border-gray-200 transition-colors"
        >
          Export SVG
        </button>
      </div>
    </div>
  )
}
