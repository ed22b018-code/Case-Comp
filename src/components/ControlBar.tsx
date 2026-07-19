import type { Therapy, ViewMode, Pane, ColorMode } from '../types/district'
import { PANES } from '../types/district'

// ── Generic segmented control ─────────────────────────────────────────────────

interface SegmentedControlProps<T extends string> {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  label: string
}

function SegmentedControl<T extends string>({ options, value, onChange, label }: SegmentedControlProps<T>) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
      <div className="flex rounded-lg bg-gray-800 p-0.5 gap-0.5">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${
              value === opt.value
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Nav tabs ──────────────────────────────────────────────────────────────────

function NavTabs({ activePane, onPaneChange }: { activePane: Pane; onPaneChange: (p: Pane) => void }) {
  return (
    <div className="flex rounded-lg bg-gray-800 p-0.5 gap-0.5">
      {PANES.map((p) => (
        <button
          key={p.value}
          onClick={() => onPaneChange(p.value)}
          className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-150 ${
            activePane === p.value
              ? 'bg-orange-500 text-white shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

// ── Option constants ───────────────────────────────────────────────────────────

const THERAPY_OPTIONS: { value: Therapy; label: string }[] = [
  { value: 'overall', label: 'Overall' },
  { value: 'chronic', label: 'Chronic' },
  { value: 'acute',   label: 'Acute'   },
]

const VIEW_OPTIONS: { value: ViewMode; label: string }[] = [
  { value: 'current', label: 'Current'       },
  { value: 'future',  label: '2030 Projected' },
  { value: 'growth',  label: 'Growth Δ'  },
]

const COLOR_MODE_OPTIONS: { value: ColorMode; label: string }[] = [
  { value: 'score',     label: 'Score'     },
  { value: 'archetype', label: 'Archetype' },
]

// ── ControlBar ────────────────────────────────────────────────────────────────

interface ControlBarProps {
  therapy:        Therapy
  view:           ViewMode
  activePane:     Pane
  colorMode:      ColorMode
  onTherapyChange:   (t: Therapy)    => void
  onViewChange:      (v: ViewMode)   => void
  onPaneChange:      (p: Pane)       => void
  onColorModeChange: (c: ColorMode)  => void
}

export function ControlBar({
  therapy, view, activePane, colorMode,
  onTherapyChange, onViewChange, onPaneChange, onColorModeChange,
}: ControlBarProps) {
  return (
    <header className="h-14 bg-gray-900 border-b border-gray-700 flex items-center px-4 gap-4 shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-6 h-6 rounded bg-orange-500 flex items-center justify-center">
          <span className="text-white text-xs font-black">SP</span>
        </div>
        <div>
          <p className="text-white text-sm font-semibold leading-tight">MAI Explorer</p>
          <p className="text-gray-500 text-[10px] leading-tight">India District Market Attractiveness</p>
        </div>
      </div>

      {/* Nav tabs */}
      <NavTabs activePane={activePane} onPaneChange={onPaneChange} />

      <div className="flex-1" />

      {/* Therapy */}
      <SegmentedControl
        label="Therapy"
        options={THERAPY_OPTIONS}
        value={therapy}
        onChange={onTherapyChange}
      />

      <div className="w-px h-6 bg-gray-700" />

      {/* View — hide for simulator (strategy controls are inside) */}
      {activePane !== 'simulator' && (
        <>
          <SegmentedControl
            label="View"
            options={VIEW_OPTIONS}
            value={view}
            onChange={onViewChange}
          />
          <div className="w-px h-6 bg-gray-700" />
        </>
      )}

      {/* Color mode — only on map pane */}
      {activePane === 'map' && (
        <SegmentedControl
          label="Color"
          options={COLOR_MODE_OPTIONS}
          value={colorMode}
          onChange={onColorModeChange}
        />
      )}
    </header>
  )
}
