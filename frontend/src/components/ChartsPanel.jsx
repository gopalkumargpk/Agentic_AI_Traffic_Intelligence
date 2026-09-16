import { TrendingUp } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, Legend
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-bright)',
        borderRadius: 8,
        padding: '8px 12px',
        fontSize: 12,
      }}>
        <p style={{ color: 'var(--text-muted)', marginBottom: 4 }}>t={Math.round(label)}s</p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color, fontFamily: 'var(--font-mono)' }}>
            {p.name}: {Number(p.value).toFixed(2)}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export default function ChartsPanel({ history, controller }) {
  const data = history.slice(-120)  // last 120 points

  return (
    <div className="card">
      <div className="card-title">
        <TrendingUp className="icon" size={14} />
        Live Performance Charts
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          Last {data.length} data points
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* Waiting time */}
        <ChartCard title="Average Waiting Time (s)" color="#f59e0b">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <defs>
                <linearGradient id="gradWait" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="sim_time" tick={{ fontSize: 10, fill: '#475569' }} tickFormatter={v => `${Math.round(v)}s`} />
              <YAxis tick={{ fontSize: 10, fill: '#475569' }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="avg_waiting_time" stroke="#f59e0b" fill="url(#gradWait)" strokeWidth={2} name="Avg Wait (s)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Queue lengths */}
        <ChartCard title="Queue Lengths (NS vs EW)" color="#6366f1">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="sim_time" tick={{ fontSize: 10, fill: '#475569' }} tickFormatter={v => `${Math.round(v)}s`} />
              <YAxis tick={{ fontSize: 10, fill: '#475569' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }} />
              <Line type="monotone" dataKey="ns_queue" stroke="#6366f1" strokeWidth={2} name="NS Queue" dot={false} />
              <Line type="monotone" dataKey="ew_queue" stroke="#22d3ee" strokeWidth={2} name="EW Queue" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Throughput */}
        <ChartCard title="Cumulative Throughput (arrived vehicles)" color="#10b981">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <defs>
                <linearGradient id="gradTP" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="sim_time" tick={{ fontSize: 10, fill: '#475569' }} tickFormatter={v => `${Math.round(v)}s`} />
              <YAxis tick={{ fontSize: 10, fill: '#475569' }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="throughput" stroke="#10b981" fill="url(#gradTP)" strokeWidth={2} name="Throughput" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Average Speed */}
        <ChartCard title="Average Speed (m/s)" color="#a855f7">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <defs>
                <linearGradient id="gradSpd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#a855f7" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="sim_time" tick={{ fontSize: 10, fill: '#475569' }} tickFormatter={v => `${Math.round(v)}s`} />
              <YAxis tick={{ fontSize: 10, fill: '#475569' }} domain={[0, 15]} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="avg_speed" stroke="#a855f7" fill="url(#gradSpd)" strokeWidth={2} name="Avg Speed (m/s)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

      </div>
    </div>
  )
}

function ChartCard({ title, color, children }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 16px',
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 600,
        color: color,
        marginBottom: 12,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}
