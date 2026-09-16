import { BarChart2 } from 'lucide-react'

const fmt = (v, dec = 2) => (v == null ? '—' : Number(v).toFixed(dec))

export default function MetricsPanel({ metrics, controller }) {
  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-title">
        <BarChart2 className="icon" size={14} />
        Performance Metrics
        <span style={{ marginLeft: 'auto' }}>
          <span className={`badge ${controller === 'agentic' ? 'badge-agentic' : 'badge-fixed'}`} style={{ fontSize: 10 }}>
            {controller === 'agentic' ? 'AI' : 'Fixed'}
          </span>
        </span>
      </div>

      {metrics ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <MetricRow
            label="Avg Waiting Time"
            value={`${fmt(metrics.average_waiting_time_s)} s`}
            maxVal={120}
            currentVal={metrics.average_waiting_time_s}
            warn={40}
            critical={80}
          />
          <MetricRow
            label="Total Waiting Time"
            value={`${fmt(metrics.total_waiting_time_s, 0)} s`}
            maxVal={50000}
            currentVal={metrics.total_waiting_time_s}
            warn={10000}
            critical={30000}
          />
          <MetricRow
            label="Max NS Queue"
            value={fmt(metrics.max_ns_queue, 0)}
            maxVal={25}
            currentVal={metrics.max_ns_queue}
            warn={10}
            critical={18}
          />
          <MetricRow
            label="Max EW Queue"
            value={fmt(metrics.max_ew_queue, 0)}
            maxVal={25}
            currentVal={metrics.max_ew_queue}
            warn={10}
            critical={18}
          />
          <MetricRow
            label="Throughput"
            value={`${metrics.throughput_vehicles ?? '—'} veh`}
            maxVal={1000}
            currentVal={metrics.throughput_vehicles}
            invert={true}
          />
          <MetricRow
            label="Avg Speed"
            value={`${fmt(metrics.average_speed_ms)} m/s`}
            maxVal={14}
            currentVal={metrics.average_speed_ms}
            invert={true}
          />

          {metrics.average_reward != null && (
            <>
              <div className="divider" />
              <MetricRow
                label="Avg Reward"
                value={`${metrics.average_reward >= 0 ? '+' : ''}${fmt(metrics.average_reward, 4)}`}
                maxVal={1}
                currentVal={Math.abs(metrics.average_reward)}
                invert={metrics.average_reward >= 0}
              />
              <MetricRow
                label="AI Decisions"
                value={metrics.num_decisions ?? '—'}
                maxVal={500}
                currentVal={metrics.num_decisions}
                invert={true}
              />
            </>
          )}
        </div>
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
          Start a simulation to see performance metrics.
        </div>
      )}
    </div>
  )
}

function MetricRow({ label, value, maxVal, currentVal, warn, critical, invert = false }) {
  const pct = Math.min((currentVal / maxVal) * 100, 100) || 0
  let fillClass = ''
  if (!invert) {
    if (currentVal >= (critical || Infinity)) fillClass = 'amber'
    else if (currentVal >= (warn || Infinity)) fillClass = ''
    else fillClass = 'green'
  } else {
    fillClass = 'green'
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{
          fontSize: 13,
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: !invert && currentVal >= (critical || Infinity) ? 'var(--accent-red)'
               : !invert && currentVal >= (warn || Infinity) ? 'var(--accent-amber)'
               : 'var(--text-primary)',
        }}>
          {value}
        </span>
      </div>
      <div className="progress-bar">
        <div className={`progress-fill ${fillClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
