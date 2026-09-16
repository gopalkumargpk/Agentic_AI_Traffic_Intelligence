import { Brain } from 'lucide-react'

const fmt = (v, dec = 3) => (v == null ? '—' : Number(v).toFixed(dec))
const fmtPct = (v) => (v == null ? '—' : `${(Number(v) * 100).toFixed(0)}%`)

const GOAL_ICONS = {
  REDUCE_WAITING_TIME:  '⏱',
  REDUCE_NS_CONGESTION: '↕',
  REDUCE_EW_CONGESTION: '↔',
  INCREASE_THROUGHPUT:  '🚀',
  BALANCE_DIRECTIONS:   '⚖',
  MAINTAIN_FLOW:        '✅',
}

const ACTION_COLORS = {
  EXTEND_GREEN_10:  'var(--accent-green)',
  SHORTEN_GREEN_10: 'var(--accent-amber)',
  HOLD_CURRENT:     'var(--accent-secondary)',
  WAIT_TRANSITION:  'var(--text-muted)',
}

export default function AgentPanel({ agentState, controller }) {
  const isFixed = controller === 'fixed'

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-title">
        <Brain className="icon" size={14} />
        Agentic AI — Decision Cycle
        {isFixed && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
            (Fixed controller — no AI decisions)
          </span>
        )}
      </div>

      {isFixed ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0' }}>
          Switch to Agentic controller to see AI decisions.
        </div>
      ) : agentState ? (
        <AgentContent data={agentState} />
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0' }}>
          Start a simulation in Agentic mode to see AI decisions here.
        </div>
      )}
    </div>
  )
}

function AgentContent({ data }) {
  const goalIcon = GOAL_ICONS[data.goal] || '🎯'
  const actionColor = ACTION_COLORS[data.selected_action] || 'var(--accent-primary)'
  const reward = data.reward ?? 0
  const rewardColor = reward >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {/* Left column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Goal */}
        <InfoBlock title="Current Goal" accent="var(--accent-primary)">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>{goalIcon}</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                {data.goal?.replace(/_/g, ' ')}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Priority: {fmtPct(data.goal_priority)}
              </div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6, lineHeight: 1.5 }}>
            {data.goal_reason}
          </div>
          <div className="progress-bar" style={{ marginTop: 8 }}>
            <div className="progress-fill" style={{ width: `${(data.goal_priority ?? 0) * 100}%` }} />
          </div>
        </InfoBlock>

        {/* Decision */}
        <InfoBlock title="Selected Action" accent={actionColor}>
          <div style={{ fontSize: 14, fontWeight: 700, color: actionColor, fontFamily: 'var(--font-mono)' }}>
            {data.selected_action}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            {data.action_description}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
            <SmallStat label="Duration" value={`${data.action_duration ?? '—'}s`} />
            <SmallStat label="Basis" value={data.decision_basis} />
            <SmallStat label="Confidence" value={fmtPct(data.confidence)} />
            <SmallStat label="Q-Value" value={fmt(data.q_value)} />
          </div>
        </InfoBlock>

        {/* Reward */}
        <InfoBlock title="Reward Signal" accent={rewardColor}>
          <div style={{ fontSize: 26, fontWeight: 800, color: rewardColor, fontFamily: 'var(--font-mono)' }}>
            {reward >= 0 ? '+' : ''}{fmt(reward)}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 10 }}>
            {data.reward_detail && Object.entries({
              'ΔWait':     data.reward_detail.waiting_time_component,
              'ΔNS Q':     data.reward_detail.ns_queue_component,
              'ΔEW Q':     data.reward_detail.ew_queue_component,
              'Throughput':data.reward_detail.throughput_component,
              'Speed':     data.reward_detail.speed_component,
              'Balance':   data.reward_detail.imbalance_component,
            }).map(([k, v]) => (
              <div key={k} style={{
                background: 'rgba(255,255,255,0.03)',
                borderRadius: 4,
                padding: '4px 6px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: v >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {v >= 0 ? '+' : ''}{fmt(v, 3)}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</div>
              </div>
            ))}
          </div>
        </InfoBlock>
      </div>

      {/* Right column: reasoning */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <InfoBlock title="Reasoning Summary" accent="var(--accent-purple)">
          <div className="reasoning-box">
            {data.reasoning_summary || 'No reasoning available yet.'}
          </div>
        </InfoBlock>

        {/* Candidates table */}
        {data.candidates && data.candidates.length > 0 && (
          <InfoBlock title="Candidate Actions" accent="var(--text-muted)">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Action', 'Phase', 'Duration', 'Score'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left',
                      padding: '4px 6px',
                      color: 'var(--text-muted)',
                      fontSize: 10,
                      fontWeight: 600,
                      letterSpacing: '0.06em',
                      borderBottom: '1px solid var(--border)',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.candidates.slice(0, 4).map((c, i) => (
                  <tr key={i} style={{
                    background: c.action_id === data.selected_action
                      ? 'rgba(99,102,241,0.08)' : 'transparent',
                  }}>
                    <td style={{ padding: '4px 6px', fontFamily: 'var(--font-mono)', color: c.action_id === data.selected_action ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                      {c.action_id === data.selected_action ? '▶ ' : ''}{c.action_id}
                    </td>
                    <td style={{ padding: '4px 6px', color: 'var(--text-muted)' }}>{c.target_phase}</td>
                    <td style={{ padding: '4px 6px', color: 'var(--text-muted)' }}>{c.duration}s</td>
                    <td style={{ padding: '4px 6px', fontFamily: 'var(--font-mono)' }}>
                      {fmt(c.estimated_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </InfoBlock>
        )}

        {/* Cycle info */}
        <div style={{ display: 'flex', gap: 10 }}>
          <SmallCard label="Cycle #" value={data.cycle_id ?? '—'} />
          <SmallCard label="Sim Time" value={`${data.sim_time?.toFixed(0) ?? '—'}s`} />
        </div>
      </div>
    </div>
  )
}

function InfoBlock({ title, accent, children }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: `1px solid rgba(255,255,255,0.06)`,
      borderLeft: `3px solid ${accent}`,
      borderRadius: 'var(--radius-sm)',
      padding: '12px 14px',
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: accent, marginBottom: 8 }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function SmallStat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function SmallCard({ label, value }) {
  return (
    <div style={{
      flex: 1,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      padding: '10px 12px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  )
}
