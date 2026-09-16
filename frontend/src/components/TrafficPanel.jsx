import { Car } from 'lucide-react'

const fmt = (v, dec = 1) => (v == null ? '—' : Number(v).toFixed(dec))

const DIRECTIONS = ['N', 'S', 'E', 'W']
const DIR_NAMES = { N: 'North', S: 'South', E: 'East', W: 'West' }

export default function TrafficPanel({ traffic }) {
  const dirs = traffic?.directions ?? {}

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-title">
        <Car className="icon" size={14} />
        Traffic State — All Approaches
      </div>

      {/* Top metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <BigMetric
          label="Avg Wait"
          value={fmt(traffic?.average_waiting_time)}
          unit="sec"
          color="amber"
        />
        <BigMetric
          label="Vehicles"
          value={traffic?.total_vehicles ?? '—'}
          unit="in network"
          color="primary"
        />
        <BigMetric
          label="Avg Speed"
          value={fmt(traffic?.average_speed)}
          unit="m/s"
          color="green"
        />
        <BigMetric
          label="Throughput"
          value={traffic?.throughput_arrived ?? '—'}
          unit="arrived"
          color="primary"
        />
      </div>

      {/* Per-direction breakdown */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Per-Direction Stats
      </div>
      <div className="direction-grid">
        {DIRECTIONS.map(d => {
          const ds = dirs[d] ?? {}
          const q = ds.queue_length ?? 0
          const maxQ = 20
          const pct = Math.min(q / maxQ * 100, 100)

          return (
            <div key={d} className="direction-item">
              <div className={`direction-label ${d}`}>{d} — {DIR_NAMES[d]}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Queue</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {ds.queue_length ?? '—'}
                </span>
              </div>
              <div className="progress-bar" style={{ marginBottom: 8 }}>
                <div
                  className={`progress-fill ${d === 'N' || d === 'S' ? '' : 'green'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Wait: {fmt(ds.waiting_time)}s</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Stopped: {ds.stopped ?? '—'}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function BigMetric({ label, value, unit, color }) {
  const colorMap = {
    primary: 'var(--grad-hero)',
    green:   'var(--grad-green)',
    amber:   'var(--grad-amber)',
  }
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontSize: 28,
        fontWeight: 800,
        background: colorMap[color] || colorMap.primary,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        lineHeight: 1,
        fontFamily: 'var(--font-mono)',
      }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
        {unit}
      </div>
    </div>
  )
}
