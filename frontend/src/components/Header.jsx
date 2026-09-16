import { Cpu, Wifi, WifiOff } from 'lucide-react'

export default function Header({ connected, controller, isRunning, usingMock }) {
  return (
    <header style={{
      background: 'linear-gradient(90deg, rgba(11,13,20,0.95) 0%, rgba(17,20,32,0.95) 100%)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(99,102,241,0.15)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{
        maxWidth: 1600,
        margin: '0 auto',
        padding: '0 24px',
        height: 64,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Logo + Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 40, height: 40,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #6366f1 0%, #22d3ee 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px rgba(99,102,241,0.4)',
          }}>
            <Cpu size={22} color="white" />
          </div>
          <div>
            <h1 style={{
              fontSize: 17,
              fontWeight: 800,
              background: 'linear-gradient(90deg, #f1f5f9 0%, #94a3b8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.01em',
            }}>
              Agentic AI Traffic Intelligence
            </h1>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              Autonomous Network Intelligence Layer · Research Prototype
            </p>
          </div>
        </div>

        {/* Right: status indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* SUMO / Mock indicator */}
          <span style={{ fontSize: 11, color: usingMock ? 'var(--text-muted)' : 'var(--accent-green)' }}>
            {usingMock ? '⚡ Engine: Mock Simulation' : '🚦 Engine: SUMO Simulation'}
          </span>

          {/* Controller mode */}
          <span className={`badge ${controller === 'agentic' ? 'badge-agentic' : 'badge-fixed'}`}>
            {controller === 'agentic' ? '🤖 Agentic AI' : '⏱ Fixed-Time'}
          </span>

          {/* Running status */}
          {isRunning && (
            <span className="badge badge-running">
              <span className="pulse-dot green" />
              RUNNING
            </span>
          )}

          {/* Backend connection */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {connected
              ? <Wifi size={14} color="var(--accent-green)" />
              : <WifiOff size={14} color="var(--accent-red)" />
            }
            <span style={{ fontSize: 11, color: connected ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
