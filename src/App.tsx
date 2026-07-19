import { useState } from 'react'
import type { Therapy, ViewMode, Pane, ColorMode } from './types/district'
import { useData } from './hooks/useData'
import { ControlBar } from './components/ControlBar'
import { MapView } from './components/MapView'
import { DistrictPanel } from './components/DistrictPanel'
import { OpportunityMatrix } from './components/OpportunityMatrix'
import { DeploymentSimulator } from './components/DeploymentSimulator'
import { RankingsTable } from './components/RankingsTable'

export default function App() {
  const [therapy,           setTherapy]    = useState<Therapy>('overall')
  const [view,              setView]       = useState<ViewMode>('current')
  const [activePane,        setActivePane] = useState<Pane>('map')
  const [colorMode,         setColorMode]  = useState<ColorMode>('score')
  const [selectedDistrictId, setSelectedId] = useState<string | null>(null)

  const { data, loading, error } = useData()

  const selectedDistrict = selectedDistrictId && data
    ? data.scoresMap.get(selectedDistrictId) ?? null
    : null

  function handleTherapyChange(t: Therapy) {
    setTherapy(t)
    setSelectedId(null)
  }

  function handlePaneChange(p: Pane) {
    setActivePane(p)
    // Keep district panel open when switching panes so the user can compare
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-white text-sm font-medium">Loading MAI Explorer…</p>
          <p className="text-gray-500 text-xs mt-1">Fetching district data</p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center max-w-sm px-4">
          <p className="text-red-400 font-semibold mb-2">Failed to load data</p>
          <p className="text-gray-400 text-sm">{error}</p>
          <p className="text-gray-500 text-xs mt-3">
            Make sure the dev server is running and <code className="bg-gray-800 px-1 rounded">data/</code> is accessible.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gray-100">
      <ControlBar
        therapy={therapy}
        view={view}
        activePane={activePane}
        colorMode={colorMode}
        onTherapyChange={handleTherapyChange}
        onViewChange={setView}
        onPaneChange={handlePaneChange}
        onColorModeChange={setColorMode}
      />

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 relative overflow-hidden">
          {activePane === 'map' && (
            <MapView
              data={data}
              therapy={therapy}
              view={view}
              colorMode={colorMode}
              selectedDistrictId={selectedDistrictId}
              onDistrictSelect={setSelectedId}
            />
          )}
          {activePane === 'matrix' && (
            <OpportunityMatrix
              data={data}
              therapy={therapy}
              selectedDistrictId={selectedDistrictId}
              onDistrictSelect={setSelectedId}
            />
          )}
          {activePane === 'simulator' && (
            <DeploymentSimulator
              data={data}
              therapy={therapy}
              selectedDistrictId={selectedDistrictId}
              onDistrictSelect={setSelectedId}
            />
          )}
          {activePane === 'rankings' && (
            <RankingsTable
              data={data}
              therapy={therapy}
              view={view}
              selectedDistrictId={selectedDistrictId}
              onDistrictSelect={setSelectedId}
            />
          )}
        </div>

        {selectedDistrict && (
          <DistrictPanel
            district={selectedDistrict}
            therapy={therapy}
            view={view}
            data={data}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  )
}
