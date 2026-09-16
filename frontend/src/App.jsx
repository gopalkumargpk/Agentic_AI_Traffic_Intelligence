import { useState, useEffect, useCallback, useRef } from 'react'
import Header from './components/Header.jsx'
import StatusBar from './components/StatusBar.jsx'
import TrafficPanel from './components/TrafficPanel.jsx'
import SignalPanel from './components/SignalPanel.jsx'
import AgentPanel from './components/AgentPanel.jsx'
import MetricsPanel from './components/MetricsPanel.jsx'
import ChartsPanel from './components/ChartsPanel.jsx'
import ComparisonPanel from './components/ComparisonPanel.jsx'
import SimulationControls from './components/SimulationControls.jsx'

const API = ''  // empty: use Vite proxy

export default function App() {
  const [status, setStatus]       = useState(null)
  const [traffic, setTraffic]     = useState(null)
  const [agentState, setAgentState] = useState(null)
  const [metrics, setMetrics]     = useState(null)
  const [history, setHistory]     = useState([])
  const [comparison, setComparison] = useState(null)
  const [error, setError]         = useState('')
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef(null)

  // ---- SSE live stream ----
  useEffect(() => {
    const connectSSE = () => {
      try {
        const es = new EventSource(`${API}/api/stream`)
        eventSourceRef.current = es

        es.onopen = () => {
          setConnected(true)
          setError('')
        }

        es.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data)
            if (data.state) setTraffic(data.state)
            if (data.cycle) setAgentState(data.cycle)
            if (data.metrics) setMetrics(data.metrics)
            setStatus(prev => ({
              ...prev,
              simulation_running: data.running,
              controller_mode: data.controller,
              sim_time: data.state?.sim_time ?? prev?.sim_time ?? 0,
            }))
          } catch (err) {
            // ignore parse errors
          }
        }

        es.onerror = () => {
          setConnected(false)
          es.close()
          setTimeout(connectSSE, 3000)
        }
      } catch (e) {
        setTimeout(connectSSE, 3000)
      }
    }

    connectSSE()
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  // ---- Poll slow-changing endpoints ----
  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/status`)
      if (!r.ok) throw new Error('Backend unreachable')
      const d = await r.json()
      setStatus(d)
      setConnected(true)
    } catch (e) {
      setConnected(false)
      setError('Cannot connect to backend — is it running on port 8000?')
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/history?limit=200`)
      const d = await r.json()
      setHistory(d.history || [])
    } catch (e) { /* ignore */ }
  }, [])

  const fetchComparison = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/comparison`)
      const d = await r.json()
      setComparison(d)
    } catch (e) { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchStatus()
    fetchHistory()
    fetchComparison()

    const slow = setInterval(() => {
      fetchStatus()
      fetchHistory()
      fetchComparison()
    }, 5000)

    return () => clearInterval(slow)
  }, [fetchStatus, fetchHistory, fetchComparison])

  // ---- Simulation control ----
  const startSimulation = async (params) => {
    try {
      const r = await fetch(`${API}/api/simulation/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Start failed')
      setError('')
      setTimeout(fetchStatus, 500)
    } catch (e) {
      setError(e.message)
    }
  }

  const stopSimulation = async () => {
    try {
      await fetch(`${API}/api/simulation/stop`, { method: 'POST' })
      setTimeout(() => { fetchStatus(); fetchComparison() }, 1000)
    } catch (e) {
      setError(e.message)
    }
  }

  const resetSimulation = async () => {
    try {
      await fetch(`${API}/api/simulation/reset`, { method: 'POST' })
      setTraffic(null)
      setAgentState(null)
      setMetrics(null)
      setHistory([])
      setTimeout(fetchStatus, 300)
    } catch (e) {
      setError(e.message)
    }
  }

  const isRunning = status?.simulation_running ?? false
  const controller = status?.controller_mode ?? 'agentic'

  return (
    <div className="app-wrapper">
      <Header connected={connected} controller={controller} isRunning={isRunning} usingMock={status?.using_mock ?? true} />

      <div className="container">
        {error && (
          <div className="error-banner" style={{ margin: '16px 0' }}>
            <span>⚠</span> {error}
          </div>
        )}

        <SimulationControls
          isRunning={isRunning}
          status={status}
          onStart={startSimulation}
          onStop={stopSimulation}
          onReset={resetSimulation}
        />
      </div>

      <div className="dashboard-grid">
        {/* Row 1: Status + Traffic + Signals */}
        <div className="col-3 animate-in">
          <StatusBar status={status} traffic={traffic} />
        </div>
        <div className="col-6 animate-in" style={{ animationDelay: '0.05s' }}>
          <TrafficPanel traffic={traffic} />
        </div>
        <div className="col-3 animate-in" style={{ animationDelay: '0.1s' }}>
          <SignalPanel traffic={traffic} />
        </div>

        {/* Row 2: Agent Panel (wide) + Metrics */}
        <div className="col-8 animate-in" style={{ animationDelay: '0.15s' }}>
          <AgentPanel agentState={agentState} controller={controller} />
        </div>
        <div className="col-4 animate-in" style={{ animationDelay: '0.2s' }}>
          <MetricsPanel metrics={metrics} controller={controller} />
        </div>

        {/* Row 3: Charts (full width) */}
        <div className="col-12 animate-in" style={{ animationDelay: '0.25s' }}>
          <ChartsPanel history={history} controller={controller} />
        </div>

        {/* Row 4: Comparison (full width) */}
        <div className="col-12 animate-in" style={{ animationDelay: '0.3s' }}>
          <ComparisonPanel comparison={comparison} />
        </div>
      </div>
    </div>
  )
}
