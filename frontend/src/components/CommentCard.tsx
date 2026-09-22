import { ThumbsUp, ShieldCheck, Shield, ShieldAlert } from 'lucide-react'
import type { Comment, Confidence } from '@/lib/types'

const confidenceConfig: Record<Confidence, { icon: typeof ShieldCheck; color: string; label: string }> = {
  high:   { icon: ShieldCheck,  color: '#10b981', label: 'High certainty' },
  medium: { icon: Shield,       color: '#f59e0b', label: 'Medium certainty' },
  low:    { icon: ShieldAlert,  color: '#6b7280', label: 'Low certainty' },
}

interface Props {
  comment: Comment
  stance: 'pro' | 'con'
}

export default function CommentCard({ comment, stance }: Props) {
  // Never crash the page on an unexpected value from the API.
  const cfg = confidenceConfig[comment.confidence] ?? confidenceConfig.medium
  const Icon = cfg.icon
  const border = stance === 'pro' ? 'border-emerald-500/20' : 'border-rose-500/20'
  const bg = stance === 'pro' ? 'bg-emerald-500/5' : 'bg-rose-500/5'

  return (
    <div className={`rounded-lg border ${border} ${bg} p-4 flex flex-col gap-2`}>
      <p className="text-sm text-slate-200 leading-relaxed">&ldquo;{comment.text}&rdquo;</p>

      <div className="flex items-center justify-between flex-wrap gap-2 mt-1">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="font-medium text-slate-400">{comment.author}</span>
          <span>{comment.date}</span>
          {comment.argument_type && (
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-slate-400 capitalize">
              {comment.argument_type.replace(/\s*\(.*\)/, '').trim()}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-slate-400">
            <ThumbsUp className="h-3 w-3" /> {comment.likes.toLocaleString()}
          </span>
          <span className="flex items-center gap-1" style={{ color: cfg.color }}>
            <Icon className="h-3 w-3" /> {cfg.label}
          </span>
        </div>
      </div>
    </div>
  )
}
