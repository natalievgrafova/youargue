import type { Channel, VideosResponse, CorpusVideo, AnalysisResponse } from './types'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API}${path}`)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const res = await fetch(url.toString(), { cache: 'no-store' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  channels: () => get<Channel[]>('/api/channels'),
  videos: (p: { channel_id?: string; lang?: string; start_date: string; end_date: string }) =>
    get<VideosResponse>('/api/videos', {
      start_date: p.start_date,
      end_date: p.end_date,
      ...(p.channel_id ? { channel_id: p.channel_id } : {}),
      ...(p.lang ? { lang: p.lang } : {}),
    }),
  requestAnalysis: (video_id: string, lang: string, title: string) =>
    post<{ video_id: string; status: string; note?: string }>('/api/analysis/request',
      { video_id, lang, title }),
  modelStatus: () =>
    get<{ languages: string[]; detail: Record<string, unknown> }>('/api/model/status', {}),
  corpusVideos: (lang: string, source: string = 'gold') =>
    get<{ videos: CorpusVideo[]; lang: string }>('/api/analysis/videos', { lang, source }),
  topics: (title: string, lang: string, source: string = 'gold') =>
    get<AnalysisResponse>('/api/analysis/topics', { title, lang, source }),
}
