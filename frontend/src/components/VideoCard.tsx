'use client'
import { useState } from 'react'
import Image from 'next/image'
import { MessageSquare, ThumbsUp, Eye, ExternalLink, Sparkles, Check, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Video } from '@/lib/types'

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'k'
  return String(n)
}

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) }
  catch { return iso }
}

export default function VideoCard({ video }: { video: Video }) {
  // The models run on a GPU elsewhere, so this records a request rather than
  // analysing on the spot; the Analysis page shows the video as queued.
  const [state, setState] = useState<'idle' | 'sending' | 'queued' | 'done' | 'error'>('idle')
  const lang = video.channel_id?.split('_')[1] ?? 'en'

  async function addToAnalysis() {
    setState('sending')
    try {
      const r = await api.requestAnalysis(video.video_id, lang, video.title)
      setState(r.status === 'done' ? 'done' : 'queued')
    } catch {
      setState('error')
    }
  }

  const label = {
    idle: 'Add to analysis',
    sending: 'Adding…',
    queued: 'Queued for analysis',
    done: 'Already analysed',
    error: 'Could not add - is the backend running?',
  }[state]

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden flex flex-col">
      <div className="relative aspect-video w-full bg-slate-800">
        {video.thumbnail ? (
          <Image src={video.thumbnail} alt={video.title} fill className="object-cover" />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-slate-600 text-sm">No thumbnail</div>
        )}
        <div
          className="absolute top-2 left-2 rounded-full px-2 py-0.5 text-[10px] font-semibold text-white"
          style={{ backgroundColor: video.channel_color }}
        >
          {video.channel_name}
        </div>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        <a
          href={video.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-slate-100 hover:text-violet-400 transition-colors line-clamp-2 flex items-start gap-1"
        >
          {video.title}
          <ExternalLink className="h-3 w-3 mt-0.5 shrink-0 text-slate-600" />
        </a>
        <p className="text-xs text-slate-500">{fmtDate(video.published_at)}</p>
        <div className="mt-auto grid grid-cols-3 gap-2">
          {[
            { icon: MessageSquare, val: video.comment_count, color: '#8b5cf6' },
            { icon: ThumbsUp, val: video.like_count, color: '#10b981' },
            { icon: Eye, val: video.view_count, color: '#06b6d4' },
          ].map(({ icon: Icon, val, color }, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5" style={{ color }} />
              <span className="text-xs text-slate-300 font-medium">{fmt(val)}</span>
            </div>
          ))}
        </div>
        <button
          onClick={addToAnalysis}
          disabled={state !== 'idle' && state !== 'error'}
          className={`mt-1 flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
            state === 'queued' || state === 'done'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 cursor-default'
              : state === 'error'
              ? 'border-red-500/30 bg-red-500/5 text-red-400'
              : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-violet-500 hover:text-violet-300'
          }`}
        >
          {state === 'sending' ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
            : state === 'queued' || state === 'done' ? <Check className="h-3.5 w-3.5" />
            : <Sparkles className="h-3.5 w-3.5" />}
          {label}
        </button>
      </div>
    </div>
  )
}
