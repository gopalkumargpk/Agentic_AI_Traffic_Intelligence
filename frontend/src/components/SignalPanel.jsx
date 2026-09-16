import { TrafficCone } from 'lucide-react'

const PHASES = {
  0: { name: 'NS GREEN',  ns: 'green', ew: 'red' },
  1: { name: 'NS YELLOW', ns: 'yellow', ew: 'red' },
  2: { name: 'ALL RED',   ns: 'red',   ew: 'red' },
  3: { name: 'EW GREEN',  ns: 'red',   ew: 'green' },
  4: { name: 'EW YELLOW', ns: 'red',   ew: 'yellow' },
  5: { name: 'ALL RED',   ns: 'red',   ew: 'red' },
}

export default function SignalPanel({ traffic }) {
  const phase = traffic?.phase ?? 0
  const info  = PHASES[phase] || PHASES[0]
  const nextSwitchIn = traffic?.next_switch_in ?? 0
  const phaseDuration = traffic?.phase_duration ?? 30
  const elapsed = phaseDuration - nextSwitchIn
  const pct = Math.min(elapsed / phaseDuration * 100, 100)

  const lightColor = (state) => {
    if (state === 'green')  return 'green-active'
    if (state === 'yellow') return 'yellow-active'
    if (state === 'red')    return 'red-active'
    return 'inactive'
  }

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-title">
        <TrafficCone className="icon" size={14} />
        Signal State
      </div>

      {/* Phase name */}
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div style={{
          fontSize: 22,
          fontWeight: 800,
          fontFamily: 'var(--font-mono)',
          background: info.ns === 'green' ? 'var(--grad-green)' :
                      info.ew === 'green' ? 'linear-gradient(135deg,#22d3ee,#6366f1)' :
                      'linear-gradient(135deg,#ef4444,#f59e0b)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}>
          {info.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
          Phase {phase} · Junction C
        </div>
      </div>

      {/* Visual traffic light representation */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: 32,
        marginBottom: 20,
      }}>
        <SignalGroup label="N–S" state={info.ns} />
        <SignalGroup label="E–W" state={info.ew} />
      </div>

      {/* Phase timer */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Phase timer</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>
            {Math.round(nextSwitchIn)}s remaining
          </span>
        </div>
        <div className="progress-bar">
          <div
            className={`progress-fill ${info.ns === 'green' ? '' : info.ew === 'green' ? 'green' : 'amber'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="divider" />

      {/* Imbalance */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
          Queue Imbalance
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--accent-primary)' }}>
            NS: {traffic?.ns_queue?.toFixed(0) ?? '—'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--accent-secondary)' }}>
            EW: {traffic?.ew_queue?.toFixed(0) ?? '—'}
          </span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${Math.min((traffic?.queue_imbalance ?? 0) * 100, 100)}%` }}
          />
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, textAlign: 'right' }}>
          {((traffic?.queue_imbalance ?? 0) * 100).toFixed(0)}% imbalance
        </div>
      </div>
    </div>
  )
}

function SignalGroup({ label, state }) {
  const colors = {
    green:  { r: 'inactive', y: 'inactive', g: 'green-active'  },
    yellow: { r: 'inactive', y: 'yellow-active', g: 'inactive' },
    red:    { r: 'red-active', y: 'inactive', g: 'inactive'    },
  }
  const c = colors[state] || colors.red

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, letterSpacing: '0.1em' }}>
        {label}
      </div>
      <div style={{
        background: 'rgba(0,0,0,0.4)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 10,
        padding: '10px 8px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <div className={`signal-light ${c.r}`} />
        <div className={`signal-light ${c.y}`} />
        <div className={`signal-light ${c.g}`} />
      </div>
    </div>
  )
}
