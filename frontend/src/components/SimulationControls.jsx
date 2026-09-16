import { useState } from 'react'
import { Play, Square, RotateCcw, Settings } from 'lucide-react'

const DEMANDS = ['low', 'medium', 'high', 'asymmetric_ns', 'asymmetric_ew']
const CONTROLLERS = ['agentic', 'fixed']

export default function SimulationControls({ isRunning, status, onStart, onStop, onReset }) {
  const [config, setConfig] = useState({
    controller: 'agentic',
    demand: 'medium',
    duration: 1800,
    seed: 42,
    decision_interval: 10,
    ns_green: 30,
    ew_green: 30,
    use_gui: false,
  })
  const [showAdvanced, setShowAdvanced] = useState(false)

  const update = (k, v) => setConfig(prev => ({ ...prev, [k]: v }))

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '16px 20px',
      margin: '16px 0',
      display: 'flex',
      alignItems: 'flex-start',
      gap: 24,
      flexWrap: 'wrap',
    }}>
      {/* Title */}
      <div style={{ minWidth: 140 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
          Simulation Controls
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary"
            disabled={isRunning}
            onClick={() => onStart(config)}
          >
            <Play size={15} />
            Start
          </button>
          <button
            className="btn btn-danger"
            disabled={!isRunning}
            onClick={onStop}
          >
            <Square size={15} />
            Stop
          </button>
          <button
            className="btn btn-secondary"
            onClick={onReset}
          >
            <RotateCcw size={14} />
            Reset
          </button>
        </div>
      </div>

      {/* Main config */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <ConfigField label="Controller">
          <select
            className="select-input"
            value={config.controller}
            onChange={e => update('controller', e.target.value)}
            disabled={isRunning}
          >
            {CONTROLLERS.map(c => (
              <option key={c} value={c}>{c === 'agentic' ? '🤖 Agentic AI' : '⏱ Fixed-Time'}</option>
            ))}
          </select>
        </ConfigField>

        <ConfigField label="Traffic Demand">
          <select
            className="select-input"
            value={config.demand}
            onChange={e => update('demand', e.target.value)}
            disabled={isRunning}
          >
            {DEMANDS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </ConfigField>

        <ConfigField label="Duration (s)">
          <select
            className="select-input"
            value={config.duration}
            onChange={e => update('duration', parseInt(e.target.value))}
            disabled={isRunning}
          >
            {[300, 600, 1200, 1800, 3600].map(d => <option key={d} value={d}>{d}s ({Math.round(d/60)} min)</option>)}
          </select>
        </ConfigField>

        <ConfigField label="Seed">
          <input
            type="number"
            className="select-input"
            value={config.seed}
            min={0}
            style={{ width: 80 }}
            onChange={e => update('seed', parseInt(e.target.value))}
            disabled={isRunning}
          />
        </ConfigField>

        <button
          className="btn btn-secondary"
          style={{ padding: '8px 12px' }}
          onClick={() => setShowAdvanced(v => !v)}
        >
          <Settings size={13} />
        </button>
      </div>

      {/* Advanced */}
      {showAdvanced && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end', width: '100%' }}>
          <ConfigField label="Decision Interval (s)">
            <input type="number" className="select-input" value={config.decision_interval} min={5} max={60}
              style={{ width: 80 }} onChange={e => update('decision_interval', parseInt(e.target.value))} disabled={isRunning} />
          </ConfigField>
          <ConfigField label="NS Green (s)">
            <input type="number" className="select-input" value={config.ns_green} min={10} max={60}
              style={{ width: 80 }} onChange={e => update('ns_green', parseInt(e.target.value))} disabled={isRunning} />
          </ConfigField>
          <ConfigField label="EW Green (s)">
            <input type="number" className="select-input" value={config.ew_green} min={10} max={60}
              style={{ width: 80 }} onChange={e => update('ew_green', parseInt(e.target.value))} disabled={isRunning} />
          </ConfigField>
        </div>
      )}
    </div>
  )
}

function ConfigField({ label, children }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 5 }}>
        {label}
      </div>
      {children}
    </div>
  )
}
