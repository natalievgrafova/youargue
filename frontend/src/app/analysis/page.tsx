'use client'
import { useState, useEffect } from 'react'
import { MessageSquare, GitBranch, Tags, BarChart2, Layers, ChevronLeft, ChevronRight, Info } from 'lucide-react'
import { api } from '@/lib/api'
import type { CorpusVideo, AnalysisResponse, Topic } from '@/lib/types'
import PipelineSteps from '@/components/PipelineSteps'
import TopicCard from '@/components/TopicCard'
import CommentCard from '@/components/CommentCard'

// `sub` names the channel and how the corpus was annotated. English and Dutch are
// human-annotated; the other three are model-annotated, and saying so on the
// selector is the only place a viewer would otherwise assume otherwise.
const LANGS = [
  { id: 'en', label: '🇬🇧 English', sub: 'BBC News · human-annotated', available: true },
  { id: 'nl', label: '🇧🇪 Dutch', sub: 'VRT NEWS · human-annotated', available: true },
  { id: 'de', label: '🇩🇪 German', sub: 'ZDFheute · AI-annotated', available: true },
  { id: 'fr', label: '🇫🇷 French', sub: 'BFMTV · AI-annotated', available: true },
  { id: 'ru', label: '🇷🇺 Russian', sub: 'BBC Russian · AI-annotated', available: true },
]

const CHANNEL_NAME: Record<string, string> = {
  en: 'BBC News', nl: 'VRT NEWS', de: 'ZDFheute', fr: 'BFMTV', ru: 'BBC Russian',
}

// English and Dutch were annotated by people. German, French and Russian were
// annotated by GPT-5.5; humans only adjudicated the cases where a second model
// disagreed. Calling both "human annotations" would misrepresent three corpora.
const ANNOTATED_BY: Record<string, string> = {
  en: 'Human annotations', nl: 'Human annotations',
  de: 'AI annotations', fr: 'AI annotations', ru: 'AI annotations',
}
const goldLabel = (l: string) => ANNOTATED_BY[l] ?? 'Reference annotations'


function useQueryParam(name: string): string {
  // Read once on mount. The page owns its state after that, so a later click on a
  // language button must not be overridden by a stale query string.
  const [v] = useState(() =>
    typeof window === 'undefined' ? '' :
    new URLSearchParams(window.location.search).get(name) ?? '')
  return v
}

export default function AnalysisPage() {
  const qLang = useQueryParam('lang')
  const qTitle = useQueryParam('title')
  const [lang, setLang] = useState(qLang && LANGS.some(l => l.id === qLang) ? qLang : 'en')
  const [videos, setVideos] = useState<CorpusVideo[]>([])
  const [videoIndex, setVideoIndex] = useState(0)
  const [selectedTitle, setSelectedTitle] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null)
  const [loadingVideos, setLoadingVideos] = useState(false)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // 'gold' shows the human annotations, 'model' shows what the trained models
  // predict. The toggle only appears for languages that have a prediction file.
  const [source, setSource] = useState<'gold' | 'model'>('gold')
  const [modelLangs, setModelLangs] = useState<string[]>([])

  useEffect(() => {
    api.modelStatus().then(r => setModelLangs(r.languages ?? [])).catch(() => setModelLangs([]))
  }, [])

  useEffect(() => {
    if (source === 'model' && !modelLangs.includes(lang)) setSource('gold')
  }, [lang, modelLangs, source])

  // Load corpus videos when lang changes
  useEffect(() => {
    setVideos([])
    setVideoIndex(0)
    setSelectedTitle('')
    setAnalysis(null)
    setSelectedTopic(null)
    setError(null)

    if (!LANGS.find(l => l.id === lang)?.available) return

    setLoadingVideos(true)
    api.corpusVideos(lang, source)
      .then(res => {
        setVideos(res.videos)
        // a title handed in by an example card: select it rather than the first video
        if (qTitle && res.videos.some(v => v.title === qTitle)) {
          const i = res.videos.findIndex(v => v.title === qTitle)
          setVideoIndex(i)
          setSelectedTitle(qTitle)
        }
      })
      .catch(() => setError('Backend unavailable. Is the FastAPI server running?'))
      .finally(() => setLoadingVideos(false))
  }, [lang, source, qTitle])

  // Load analysis when title changes
  useEffect(() => {
    if (!selectedTitle) return
    setAnalysis(null)
    setSelectedTopic(null)
    setLoadingAnalysis(true)
    setError(null)

    api.topics(selectedTitle, lang, source)
      .then(res => setAnalysis(res))
      .catch(() => setError('Failed to load analysis for this video.'))
      .finally(() => setLoadingAnalysis(false))
  }, [selectedTitle, lang, source])

  const pipelineStep = !selectedTitle ? 0 : !analysis ? 1 : !selectedTopic ? 3 : 4

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-8">
      {/* Hero */}
      <div>
        <h1 className="text-3xl font-bold text-white">Argument Mining</h1>
        <p className="mt-1 text-slate-400 text-sm max-w-xl">
          Explore how public opinion distributes across topics in political YouTube discussions.
          Select a video from our annotated corpus to see PRO and CON stances per topic.
        </p>
      </div>

      {/* Pipeline stepper */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <PipelineSteps activeStep={pipelineStep} />
      </div>

      {/* Language tabs */}
      <div className="flex gap-2 flex-wrap">
        {LANGS.map(l => (
          <button
            key={l.id}
            disabled={!l.available}
            onClick={() => setLang(l.id)}
            className={`px-4 py-2 rounded-xl border text-sm font-medium transition-all ${
              lang === l.id
                ? 'border-violet-500 bg-violet-500/10 text-violet-300'
                : l.available
                ? 'border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-200 bg-slate-900/60'
                : 'border-slate-800/50 text-slate-700 cursor-not-allowed bg-slate-900/20'
            }`}
          >
            <span className="block">{l.label}</span>
            <span className="block text-[10px] font-normal mt-0.5 opacity-70">{l.sub}</span>
          </button>
        ))}
      </div>

      {modelLangs.includes(lang) ? (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-400">Showing:</span>
          {(['gold', 'model'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className={`rounded-lg px-3 py-1.5 border transition ${
                source === s
                  ? 'border-violet-500/40 bg-violet-500/10 text-violet-300'
                  : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              {s === 'gold' ? goldLabel(lang) : 'Model predictions'}
            </button>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-500">
          {goldLabel(lang)}. Model predictions for {lang.toUpperCase()} are not loaded
          yet — run <code className="text-slate-400">tools/fetch_predictions.sh</code> and
          restart the backend.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400 flex items-center gap-2">
          <Info className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Video selector */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <Layers className="h-4 w-4 text-violet-400" /> Select a Video
        </h2>

        {loadingVideos && (
          <div className="text-sm text-slate-500 animate-pulse">Loading corpus…</div>
        )}

        {!loadingVideos && videos.length > 0 && (() => {
          const PAGE = 5
          const page = Math.floor(videoIndex / PAGE)
          const totalPages = Math.ceil(videos.length / PAGE)
          const pageVideos = videos.slice(page * PAGE, page * PAGE + PAGE)
          const go = (delta: number) => {
            const nextPage = (page + delta + totalPages) % totalPages
            setVideoIndex(nextPage * PAGE)
          }
          return (
            <div className="space-y-3">
              <div className="grid grid-cols-5 gap-2">
                {pageVideos.map((v, i) => {
                  // A video requested from the dashboard shows here immediately,
                  // greyed and marked, rather than being invisible until the
                  // models have run on it.
                  const pending = v.status === 'queued' || v.status === 'running'
                  return (
                  <button
                    key={v.title}
                    disabled={pending}
                    title={pending ? 'Queued for analysis - not scored yet' : undefined}
                    onClick={() => {
                      if (pending) return
                      setVideoIndex(page * PAGE + i)
                      setSelectedTitle(v.title)
                      setAnalysis(null)
                      setSelectedTopic(null)
                    }}
                    className={`rounded-lg border px-3 py-3 text-left transition-all flex flex-col justify-between min-h-[110px] ${
                      pending
                        ? 'border-slate-800 bg-slate-900/40 opacity-50 cursor-not-allowed'
                        : selectedTitle === v.title
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-slate-700 bg-slate-800 hover:border-violet-500 hover:bg-slate-800/80'
                    }`}
                  >
                    <p className="text-xs font-medium text-slate-200 leading-snug">{v.title}</p>
                    {pending ? (
                      <p className="text-[10px] text-amber-400/80 mt-2 flex items-center gap-1">
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                        {v.status === 'running' ? 'Analysing…' : 'Queued for analysis'}
                      </p>
                    ) : (
                      <p className="text-[10px] text-slate-500 mt-2">{v.comment_count.toLocaleString()} comments</p>
                    )}
                  </button>
                )})}
              </div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => go(-1)}
                  className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:border-violet-500 hover:text-violet-300 transition-colors"
                >
                  <ChevronLeft className="h-3.5 w-3.5" /> Prev
                </button>
                <p className="text-xs text-slate-600">
                  {page * PAGE + 1}–{Math.min(page * PAGE + PAGE, videos.length)} of {videos.length} videos · click a card to analyse
                </p>
                <button
                  onClick={() => go(+1)}
                  className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:border-violet-500 hover:text-violet-300 transition-colors"
                >
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )
        })()}
      </div>

      {/* Analysis */}
      {loadingAnalysis && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-10 text-center text-sm text-slate-500 animate-pulse">
          Running pipeline…
        </div>
      )}

      {analysis && (
        <>
          {/* Video stats */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
            <h2 className="text-base font-semibold text-white mb-1 line-clamp-2">{analysis.title}</h2>
            <p className="text-xs text-slate-500 mb-5 uppercase tracking-wider">
              {CHANNEL_NAME[lang] ?? lang.toUpperCase()} · {lang === 'en' || lang === 'nl' ? 'Annotated corpus' : 'AI-annotated corpus'}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { icon: MessageSquare, label: 'Comments',    val: analysis.total_comments, color: '#8b5cf6' },
                { icon: GitBranch,     label: 'Threads',     val: analysis.thread_count,   color: '#06b6d4' },
                { icon: Tags,          label: 'Topics Found',val: analysis.topic_count,    color: '#10b981' },
                { icon: BarChart2,     label: 'Arguments',   val: analysis.topics.reduce((s, t) => s + t.total, 0), color: '#f59e0b' },
              ].map(({ icon: Icon, label, val, color }) => (
                <div key={label} className="rounded-lg bg-slate-800/50 p-3 flex items-center gap-3">
                  <Icon className="h-4 w-4 shrink-0" style={{ color }} />
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</p>
                    <p className="text-lg font-bold text-white">{val}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Topics grid */}
          <div>
            <h2 className="text-sm font-semibold text-white mb-3">
              Topics Detected — click a topic to explore stances
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {analysis.topics.map(topic => (
                <TopicCard
                  key={topic.topic}
                  topic={topic}
                  selected={selectedTopic?.topic === topic.topic}
                  onClick={() => setSelectedTopic(selectedTopic?.topic === topic.topic ? null : topic)}
                />
              ))}
            </div>
          </div>

          {/* Topic deep dive */}
          {selectedTopic && (
            <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-6 space-y-6">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <h2 className="text-lg font-bold text-white capitalize">{selectedTopic.topic}</h2>
                  <span className="text-xs text-slate-500">{selectedTopic.total} relevant comments</span>
                </div>
                <p className="text-xs text-slate-500 mb-4">
                  Filtered from {analysis.total_comments} total ·{' '}
                  {analysis.total_comments - selectedTopic.total} comments not relevant to this topic
                </p>

                {/* Big stance bar */}
                <div className="rounded-xl overflow-hidden h-8 flex gap-1">
                  <div
                    className="flex items-center justify-center text-xs font-bold text-white transition-all"
                    style={{ width: `${selectedTopic.pro_pct}%`, backgroundColor: '#10b981' }}
                  >
                    {selectedTopic.pro_pct >= 15 && `PRO ${selectedTopic.pro_pct}%`}
                  </div>
                  <div
                    className="flex items-center justify-center text-xs font-bold text-white transition-all"
                    style={{ width: `${selectedTopic.con_pct}%`, backgroundColor: '#f43f5e' }}
                  >
                    {selectedTopic.con_pct >= 15 && `CON ${selectedTopic.con_pct}%`}
                  </div>
                </div>

                <div className="flex justify-between mt-2">
                  <span className="text-sm font-semibold text-emerald-500">
                    PRO — {selectedTopic.pro_count} comments ({selectedTopic.pro_pct}%)
                  </span>
                  <span className="text-sm font-semibold text-rose-500">
                    CON — {selectedTopic.con_count} comments ({selectedTopic.con_pct}%)
                  </span>
                </div>
              </div>

              {/* Comments columns */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* PRO */}
                <div>
                  <h3 className="text-sm font-semibold text-emerald-500 mb-3 flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-emerald-500" />
                    Top PRO Arguments
                  </h3>
                  <div className="space-y-3">
                    {selectedTopic.pro_comments.length > 0 ? (
                      selectedTopic.pro_comments.map(c => (
                        <CommentCard key={c.comment_id} comment={c} stance="pro" />
                      ))
                    ) : (
                      <p className="text-sm text-slate-600 italic">No PRO comments found.</p>
                    )}
                  </div>
                </div>

                {/* CON */}
                <div>
                  <h3 className="text-sm font-semibold text-rose-500 mb-3 flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-rose-500" />
                    Top CON Arguments
                  </h3>
                  <div className="space-y-3">
                    {selectedTopic.con_comments.length > 0 ? (
                      selectedTopic.con_comments.map(c => (
                        <CommentCard key={c.comment_id} comment={c} stance="con" />
                      ))
                    ) : (
                      <p className="text-sm text-slate-600 italic">No CON comments found.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
