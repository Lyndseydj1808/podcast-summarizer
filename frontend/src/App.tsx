import { useState } from 'react'
import { NavLink, Route, BrowserRouter, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Summaries from './pages/Summaries'
import { API_BASE } from './api'
import './App.css'

function App() {
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleProcess(episodeId: string) {
    setProcessingId(episodeId)
    setActionError(null)
    try {
      const res = await fetch(`${API_BASE}/episodes/${episodeId}/process`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `Processing failed (${res.status})`)
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setProcessingId(null)
    }
  }

  return (
    <BrowserRouter>
      <div className="app">
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
            Dashboard
          </NavLink>
          <NavLink to="/summaries" className={({ isActive }) => (isActive ? 'active' : '')}>
            Summaries
          </NavLink>
        </nav>

        {actionError && <p className="error">{actionError}</p>}
        {processingId && (
          <p className="processing-banner">
            <span className="spinner" /> Processing an episode, this may take a few minutes.
            Please don't refresh or close this tab until it finishes.
          </p>
        )}

        <Routes>
          <Route
            path="/"
            element={<Dashboard processingId={processingId} onProcess={handleProcess} />}
          />
          <Route path="/summaries" element={<Summaries />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
