import { useEffect, useState } from 'react'
import { API_BASE, type ProcessedEpisode } from '../api'

function Summaries() {
  const [processed, setProcessed] = useState<ProcessedEpisode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/episodes/processed`)
      .then((res) => {
        if (!res.ok) throw new Error('Could not reach the backend. Is it running?')
        return res.json()
      })
      .then(setProcessed)
      .catch((e) => setError(e instanceof Error ? e.message : 'Something went wrong'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <h1>Summaries</h1>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading...</p>}
      {!loading && processed.length === 0 && (
        <p className="empty">Nothing processed yet, summaries will show up here once episodes go through the pipeline.</p>
      )}

      <ul className="summary-list">
        {processed.map((ep, index) => (
          <li key={index}>
            <details>
              <summary>
                <strong>{ep.episode_name}</strong>
                <div className="meta">
                  {ep.show_name ?? 'Unknown show'} &middot;{' '}
                  {new Date(ep.processed_at).toLocaleString()}
                </div>
              </summary>
              <p className="summary-text">
                {ep.summary ?? 'No summary saved for this one (processed before this feature was added).'}
              </p>
            </details>
          </li>
        ))}
      </ul>
    </>
  )
}

export default Summaries
