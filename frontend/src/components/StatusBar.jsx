import { Activity } from 'lucide-react'

const fmt = (v, dec = 1) => (v == null ? '—' : Number(v).toFixed(dec))

export default function StatusBar({ status, traffic }) {
  const simTime = traffic?.sim_time ?? status?.sim_time ?? 0
  const mins = Math.floor(simTime / 60)
  const secs = Math.floor(simTime % 60)
  const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`

  const congestion = traffic?.congestion_level ?? 'LOW'

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-title">
        <Activity className="icon" size={14} />
        System Status
      </div>

      {/* Simulation time */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
          SIMULATION TIME
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 28,
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '0.05em',
        }}>
          {timeStr}
        </div>
      </div>

      <div className="divider" />

      {/* Congestion level */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
          CONGESTION LEVEL
        </div>
        <div className={`congestion-${congestion}`} style={{ fontSize: 18, fontWeight: 700 }}>
          ● {congestion}
        </div>
      </div>

      {/* Key quick stats */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <StatusRow label="Total Vehicles" value={traffic?.total_vehicles ?? '—'} />
        <StatusRow label="Avg Speed" value={traffic?.average_speed != null ? `${fmt(traffic.average_speed)} m/s` : '—'} />
        <StatusRow label="Stopped" value={traffic?.total_stopped ?? '—'} />
        <StatusRow label="Run ID" value={status?.run_id ?? '—'} />
      </div>

      <div className="divider" />

      {/* SUMO indicator */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
        {status?.sumo_available
          ? '✅ SUMO Connected'
          : '⚡ Mock Simulation Active'}
      </div>
    </div>
  )
}

function StatusRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>
        {value}
      </span>
    </div>
  )
}
