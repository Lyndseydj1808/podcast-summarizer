export const API_BASE = 'http://127.0.0.1:8000'

export interface QueuedEpisode {
  id: string
  name: string
  show_name: string | null
  duration_ms: number
}

export interface ProcessedEpisode {
  episode_name: string
  show_name: string | null
  processed_at: string
  summary: string | null
}
