import { useEffect, useRef, useState } from 'react'
import { API_BASE, type ProcessedEpisode, type QueuedEpisode } from '../api'

interface DashboardProps {
  processingId: string | null
  onProcess: (episodeId: string) => Promise<void>
}

function Dashboard({ processingId, onProcess }: DashboardProps) {
  const [queue, setQueue] = useState<QueuedEpisode[]>([])
  const [processed, setProcessed] = useState<ProcessedEpisode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const wasProcessing = useRef(false)

  useEffect(() => {
    loadData()
  }, [])

  // processingId lives in App now, so it survives navigating away and back.
  // If it just flipped from "something in progress" to "done" while we're
  // sitting on this page, refresh the lists to show the result.
  useEffect(() => {
    if (wasProcessing.current && !processingId) {
      loadData()
    }
    wasProcessing.current = processingId !== null
  }, [processingId])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [queueRes, processedRes] = await Promise.all([
        fetch(`${API_BASE}/episodes/queue`),
        fetch(`${API_BASE}/episodes/processed`),
      ])
      if (!queueRes.ok || !processedRes.ok) {
        throw new Error('Could not reach the backend. Is it running?')
      }
      setQueue(await queueRes.json())
      setProcessed(await processedRes.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="header">
        <h1>Podcast Summarizer</h1>
        <a className="connect-button" href={`${API_BASE}/login`}>
          Connect Spotify
        </a>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading...</p>}

      <section>
        <h2>Queue ({queue.length})</h2>
        {queue.length === 0 && !loading && <p className="empty">Nothing queued right now.</p>}
        <ul>
          {queue.map((ep) => (
            <li key={ep.id} className="queue-item">
              <div>
                <strong>{ep.name}</strong>
                <div className="meta">{ep.show_name ?? 'Unknown show'}</div>
              </div>
              <button
                onClick={() => onProcess(ep.id)}
                disabled={processingId !== null}
                className={processingId === ep.id ? 'processing' : ''}
              >
                {processingId === ep.id ? (
                  <>
                    <span className="spinner" /> Processing…
                  </>
                ) : (
                  'Process now'
                )}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Processed ({processed.length})</h2>
        {processed.length === 0 && !loading && <p className="empty">Nothing processed yet.</p>}
        <ul>
          {processed.map((ep, index) => (
            <li key={index}>
              <strong>{ep.episode_name}</strong>
              <div className="meta">
                {ep.show_name ?? 'Unknown show'} &middot;{' '}
                {new Date(ep.processed_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

export default Dashboard
