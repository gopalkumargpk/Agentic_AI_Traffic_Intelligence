import { GitCompare } from 'lucide-react'

const fmt = (v, dec = 2) => (v == null ? '—' : Number(v).toFixed(dec))

export default function ComparisonPanel({ comparison }) {
  const rows = comparison?.rows ?? []

  return (
    <div className="card">
      <div className="card-title">
        <GitCompare className="icon" size={14} />
        Fixed-Time vs Agentic AI — Experiment Comparison
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          {comparison?.summary || 'Run both controllers to populate'}
        </span>
      </div>

      <table className="comparison-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Fixed-Time Controller</th>
            <th>Agentic AI Controller</th>
            <th>Unit</th>
            <th>Improvement</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const imp = row.improvement_pct
            const isPositive = imp != null && imp > 0
            const isNegative = imp != null && imp < 0

            // For throughput and speed, higher=better (improvement_pct shows Fixed→AI change)
            const throughputLike = row.metric.includes('Throughput') || row.metric.includes('Speed')
            const goodPositive = throughputLike ? isPositive : isNegative
            const impClass = goodPositive ? 'improvement-positive'
                           : (!goodPositive && imp != null && imp !== 0) ? 'improvement-negative'
                           : ''

            const impStr = imp == null ? '—'
                         : throughputLike
                           ? (isPositive ? `▲ +${imp}%` : isNegative ? `▼ ${imp}%` : '0%')
                           : (isNegative ? `▼ ${Math.abs(imp)}% better` : isPositive ? `▲ +${imp}% worse` : '0%')

            return (
              <tr key={i}>
                <td style={{ color: 'var(--text-primary)', fontWeight: 500, fontFamily: 'var(--font-sans)', fontSize: 13 }}>
                  {row.metric}
                </td>
                <td style={{ color: 'var(--accent-amber)' }}>
                  {fmt(row.fixed)}
                </td>
                <td style={{ color: 'var(--accent-primary)' }}>
                  {fmt(row.agentic)}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {row.unit}
                </td>
                <td className={impClass} style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {impStr}
                </td>
              </tr>
            )
          })}

          {rows.length === 0 && (
            <tr>
              <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                Run experiments with both controllers to see comparison here.
                <br />
                <span style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
                  python run_experiment.py --controller fixed<br />
                  python run_experiment.py --controller agentic
                </span>
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {rows.length > 0 && (
        <div style={{
          marginTop: 16,
          display: 'flex',
          gap: 24,
          padding: '12px 16px',
          background: 'rgba(99,102,241,0.05)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid rgba(99,102,241,0.15)',
        }}>
          <Legend color="var(--accent-amber)" label="Fixed-Time" />
          <Legend color="var(--accent-primary)" label="Agentic AI" />
          <Legend color="var(--accent-green)" label="AI Improvement" />
          <Legend color="var(--accent-red)" label="AI Regression" />
        </div>
      )}
    </div>
  )
}

function Legend({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</span>
    </div>
  )
}
