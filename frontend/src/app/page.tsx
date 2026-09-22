'use client'
import { useState, useCallback, useEffect } from 'react'
import { Film, MessageSquare, ThumbsUp, Globe, RefreshCw, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import type { VideosResponse, Video, ChannelStats } from '@/lib/types'
import StatsCard from '@/components/StatsCard'
import VideoCard from '@/components/VideoCard'
import TopVideosChart from '@/components/charts/TopVideosChart'
import ChannelCompareChart from '@/components/charts/ChannelCompareChart'
import ChannelShareChart from '@/components/charts/ChannelShareChart'

const STOP = new Set(['the','and','for','with','from','that','this','have','will','been','were','they','their','them','what','into','over','after','before','about','more','also','just','then','than','when','where','how','why','all','some','any','out','not','but','are','was','has','had','did','does','may','can','its','says','said','amid','amid','new','amid'])

const VIDEOS_PER_PAGE = 5   // matches the xl grid, so a page is one row

function extractTopics(videos: Video[], topN = 10) {
  const counts: Record<string, number> = {}
  for (const v of videos) {
    const words = v.title.toLowerCase().replace(/[^a-z\s]/g, ' ').split(/\s+/).filter(w => w.length > 3 && !STOP.has(w))
    const seen = new Set<string>()
    for (let i = 0; i < words.length - 1; i++) {
      const bg = `${words[i]} ${words[i + 1]}`
      if (!seen.has(bg)) { counts[bg] = (counts[bg] || 0) + 1; seen.add(bg) }
    }
    for (const w of words) {
      if (!seen.has(w)) { counts[w] = (counts[w] || 0) + 1; seen.add(w) }
    }
  }
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])
  const max = sorted[0]?.[1] ?? 1
  return sorted.slice(0, topN).map(([phrase, count]) => ({
    label: phrase.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
    count,
    barPct: Math.round(count / max * 100),
    vidPct: Math.round(count / Math.max(videos.length, 1) * 100),
  }))
}

const CHANNELS = [
  { id: '', label: 'All Channels', color: '#8b5cf6' },
  { id: 'bbc_en', label: 'BBC News', color: '#ef4444' },
  { id: 'vrt_nl', label: 'VRT NEWS', color: '#f97316' },
  { id: 'bbc_ru', label: 'BBC Russian', color: '#3b82f6' },
  { id: 'zdf_de', label: 'ZDFheute', color: '#eab308' },
]

function today() { return new Date().toISOString().slice(0, 10) }
function monthAgo() {
  const d = new Date()
  d.setMonth(d.getMonth() - 1)
  return d.toISOString().slice(0, 10)
}

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'k'
  return String(n)
}

export default function DashboardPage() {
  const [channel, setChannel] = useState('')
  // Computed after mount, not during render: the server prerender and the
  // client would otherwise produce different dates and React reports a
  // hydration mismatch.
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  useEffect(() => {
    setStartDate(monthAgo())
    setEndDate(today())
  }, [])
  const [data, setData] = useState<VideosResponse | null>(null)
  const [videoPage, setVideoPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.videos({ channel_id: channel || undefined, start_date: startDate, end_date: endDate })
      setData(res)
      setVideoPage(0)
    } catch (e) {
      setError('Could not reach the backend. Make sure the FastAPI server is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [channel, startDate, endDate])

  const stats = data?.channel_stats ?? {}
  const activeStats = Object.values(stats).filter((s: ChannelStats) => s.video_count > 0)
  const videos: Video[] = data?.videos ?? []
  // The stat cards compare every channel, so the header counts only the channels
  // the current selection actually returned.
  const shownChannels = new Set(videos.map(v => v.channel_id)).size

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-8">
      {/* Hero */}
      <div>
        <h1 className="text-3xl font-bold text-white">Political Opinion Monitoring</h1>
        <p className="mt-1 text-slate-400 text-sm max-w-xl">
          Real-time insights into comment activity, engagement patterns, and discussion dynamics
          across multilingual political news channels on YouTube.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {CHANNELS.map(ch => (
          <button
            key={ch.id}
            onClick={() => setChannel(ch.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-all ${
              channel === ch.id
                ? 'text-white border-current'
                : 'text-slate-400 border-slate-800 hover:border-slate-600 hover:text-slate-200'
            }`}
            style={channel === ch.id ? { color: ch.color, borderColor: ch.color, backgroundColor: ch.color + '15' } : {}}
          >
            {ch.label}
          </button>
        ))}

        <div className="flex items-center gap-2 ml-auto flex-wrap">
          <input
            type="date"
            value={startDate}
            max={endDate}
            onChange={e => setStartDate(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
          />
          <span className="text-slate-600 text-sm">to</span>
          <input
            type="date"
            value={endDate}
            min={startDate}
            onChange={e => setEndDate(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
          />
          <button
            onClick={fetch}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-1.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-60 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Fetching…' : 'Fetch Data'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 py-20 text-center">
          <Globe className="mx-auto h-12 w-12 text-slate-700 mb-4" />
          <p className="text-slate-400 font-medium">Select a date range and click Fetch Data</p>
          <p className="text-slate-600 text-sm mt-1">
            Retrieves the most-discussed videos from BBC, VRT, BBC Russian and ZDFheute
          </p>
        </div>
      )}

      {data && (
        <>
          {/* Stats row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard label="Videos Found" value={fmt(data.total_videos)} icon={Film} color="#8b5cf6"
              sub={shownChannels === 1
                ? (Object.values(stats).find((s: ChannelStats) => s.id === videos[0]?.channel_id)?.name ?? 'one channel')
                : `across ${shownChannels} channels`} />
            <StatsCard label="Total Comments" value={fmt(data.total_comments)} icon={MessageSquare} color="#10b981" />
            <StatsCard label="Total Views" value={fmt(data.total_views)} icon={Globe} color="#06b6d4" />
            <StatsCard
              label="Most Active"
              value={activeStats.sort((a, b) => b.total_comments - a.total_comments)[0]?.name ?? '—'}
              icon={ThumbsUp}
              color="#f59e0b"
              sub="by comment volume"
            />
          </div>

          {/* Channel stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.values(stats).map((s: ChannelStats) => (
              <div key={s.id} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="text-xs font-semibold text-slate-300">{s.name}</span>
                </div>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between text-slate-400">
                    <span>Videos</span><span className="text-white font-medium">{s.video_count}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Comments</span><span className="text-white font-medium">{fmt(s.total_comments)}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Avg / video</span><span className="text-white font-medium">{fmt(s.avg_comments)}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Likes</span><span className="text-white font-medium">{fmt(s.total_likes)}</span>
                  </div>
                </div>
                {s.video_count > 0 && (
                  <div className="mt-3 h-1 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (s.total_comments / (data?.total_comments || 1)) * 100)}%`,
                        backgroundColor: s.color,
                      }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Charts */}
          {videos.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Top videos chart */}
              <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                <h2 className="text-sm font-semibold text-white mb-1">Top 10 Most Commented Videos</h2>
                <p className="text-xs text-slate-500 mb-5">Comments sorted by discussion volume</p>
                <TopVideosChart videos={videos} />
              </div>

              {/* Channel share (all) or Hot Topics (single channel) */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                {channel === '' ? (
                  <>
                    <h2 className="text-sm font-semibold text-white mb-1">Comment Share by Channel</h2>
                    <p className="text-xs text-slate-500 mb-5">Distribution of discussion volume</p>
                    <ChannelShareChart stats={stats} />
                  </>
                ) : (() => {
                    const topics = extractTopics(videos, 10)
                    return (
                      <>
                        <h2 className="text-sm font-semibold text-white mb-1">Most Discussed Topics</h2>
                        <p className="text-xs text-slate-500 mb-4">
                          Keywords from video titles · {videos.length} videos
                        </p>
                        <div className="space-y-2.5 overflow-y-auto" style={{ maxHeight: 340 }}>
                          {topics.map((t, i) => (
                            <div key={t.label}>
                              <div className="flex justify-between text-xs mb-1">
                                <span className="text-slate-300 font-medium">{t.label}</span>
                                <span className="text-slate-500">{t.count} video{t.count !== 1 ? 's' : ''}</span>
                              </div>
                              <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all"
                                  style={{ width: `${t.barPct}%`, backgroundColor: i === 0 ? '#8b5cf6' : i < 3 ? '#6d28d9' : '#4c1d95' }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </>
                    )
                  })()
                }
              </div>
            </div>
          )}

          {/* Engagement comparison */}
          {activeStats.length > 1 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-sm font-semibold text-white mb-1">Engagement Comparison by Channel</h2>
              <p className="text-xs text-slate-500 mb-5">Average comments and likes per video</p>
              <ChannelCompareChart stats={stats} />
            </div>
          )}

          {/* Video cards. The whole date range is returned, not just the top
              few, so the list is paged rather than truncated. */}
          {videos.length > 0 && (() => {
            const pages = Math.ceil(videos.length / VIDEOS_PER_PAGE)
            const page = Math.min(videoPage, pages - 1)
            const shown = videos.slice(page * VIDEOS_PER_PAGE, (page + 1) * VIDEOS_PER_PAGE)
            return (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-white">
                    Videos by Discussion Activity
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      {page * VIDEOS_PER_PAGE + 1}&ndash;{page * VIDEOS_PER_PAGE + shown.length} of {videos.length}
                    </span>
                  </h2>
                  {pages > 1 && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setVideoPage(p => Math.max(0, p - 1))}
                        disabled={page === 0}
                        aria-label="Previous videos"
                        className="rounded-lg border border-slate-800 bg-slate-900/60 p-1.5 text-slate-400
                                   enabled:hover:text-slate-200 enabled:hover:border-slate-700
                                   disabled:opacity-30 disabled:cursor-not-allowed transition"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <span className="px-2 text-xs text-slate-500 tabular-nums">
                        {page + 1} / {pages}
                      </span>
                      <button
                        onClick={() => setVideoPage(p => Math.min(pages - 1, p + 1))}
                        disabled={page >= pages - 1}
                        aria-label="Next videos"
                        className="rounded-lg border border-slate-800 bg-slate-900/60 p-1.5 text-slate-400
                                   enabled:hover:text-slate-200 enabled:hover:border-slate-700
                                   disabled:opacity-30 disabled:cursor-not-allowed transition"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
                  {shown.map(v => (
                    <VideoCard key={v.video_id} video={v} />
                  ))}
                </div>
              </div>
            )
          })()}
        </>
      )}
    </div>
  )
}
